# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Util to perform server-specific docker operations."""

import time
from pathlib import Path
from typing import NoReturn

import typer

from deepfellow.common.config import read_env_file_to_dict
from deepfellow.common.defaults import DOCKER_COMPOSE_CONFIG_FILENAME, NightshiftModeChoice
from deepfellow.common.docker import (
    DockerError,
    ensure_network,
    get_docker_network,
    is_service_running,
    is_service_running_or_raise,
    load_compose_file,
    print_docker_status,
    resolve_compose_volume_name,
    volume_exists,
)
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.system import run
from deepfellow.server.utils.time import is_within_shift_window

MONGO_AUTH_FAILURE_SIGNATURES = ("OperationFailure", "Authentication failed")

NIGHTSHIFT_NOT_INSTALLED_HINT = (
    "This install has no Nightshift worker (it was created before Nightshift existed). "
    "Run `deepfellow server install` to add it."
)


def has_nightshift_service(directory: Path) -> bool:
    """Whether this install's compose file defines the `nightshift` service.

    Installs created before Nightshift existed don't have it, and every `docker compose ... nightshift`
    call against them fails with `no such service: nightshift`.
    """
    compose = load_compose_file(directory / DOCKER_COMPOSE_CONFIG_FILENAME)
    return "nightshift" in compose.get("services", {})


def assert_nightshift_installed(directory: Path) -> None:
    """Exit with a hint to run `server install` if this install has no Nightshift worker."""
    if not has_nightshift_service(directory):
        echo.error(NIGHTSHIFT_NOT_INSTALLED_HINT)
        raise typer.Exit(1)


def service_running_or_exit(service: str, directory: Path) -> bool:
    """Whether a Compose service is running; stops the command if that can't be determined.

    For decisions (start/stop/refuse) - a failing `docker compose ps` must not be read as "not
    running", unlike the display-only `is_service_running()`.
    """
    try:
        return is_service_running_or_raise(service, cwd=directory)
    except DockerError as exc:
        echo.error(f"Could not check whether the {service} service is running: {exc}")
        reraise_if_debug(exc)


def wait_for_docker(timeout_seconds: float, poll_interval_seconds: float = 5) -> bool:
    """Wait until the Docker daemon answers, for at most `timeout_seconds`.

    Meant for the scheduled Nightshift action: a user-level systemd unit can't be ordered after the
    system `docker.service`, so right after boot it may fire before the daemon is up.

    Returns:
        True as soon as `docker info` succeeds, False if the daemon never answered in time.
    """
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            run(["docker", "info"], raises=DockerError, quiet=True)
        except DockerError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll_interval_seconds)
        else:
            return True


def wait_for_service_running(
    service: str, directory: Path, timeout_seconds: float, poll_interval_seconds: float = 5
) -> bool:
    """Wait until a Compose service is running, for at most `timeout_seconds`.

    Checks at least once, so a zero timeout is a plain check. A `docker compose ps` failure stops
    the command (see `service_running_or_exit()`) instead of being retried as "not running yet".

    Returns:
        True as soon as the service is running, False if it never came up in time.
    """
    deadline = time.monotonic() + timeout_seconds
    while not service_running_or_exit(service, directory):
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_interval_seconds)
    return True


def _nightshift_should_be_up(directory: Path) -> bool:
    """Whether Nightshift should be running right now, purely from `.env` + the clock.

    `always` mode: always. `shift` mode: only within its configured [start, stop) window -
    conservatively "up" if the schedule is missing/incomplete/malformed, rather than silently
    stuck down.
    """
    env_content = read_env_file_to_dict(directory / ".env")
    if env_content.get("df_nightshift_mode") != NightshiftModeChoice.shift.value:
        return True
    start = str(env_content.get("df_nightshift_start", ""))
    stop = str(env_content.get("df_nightshift_stop", ""))
    if not start or not stop:
        return True
    try:
        return is_within_shift_window(start, stop)
    except ValueError:
        # A hand-edited or otherwise corrupted .env bypasses the CLI's own HH:MM validation -
        # this is the one path that can't be caught earlier, so fail the same conservative way
        # as the missing-schedule case above rather than crashing every start_server()/status call.
        return True


def _nightshift_should_stay_down(directory: Path) -> bool:
    """Whether Nightshift is in shift mode and the current local time is outside its window.

    Computed purely from `.env` + the clock - no container inspection needed at all - so
    `start_server()` can tell `docker compose up` to never bring the worker up in the first place
    (via `--scale nightshift=0`), instead of starting it along with everything else and then
    immediately stopping it back down.
    """
    return not _nightshift_should_be_up(directory)


def reconcile_nightshift_running_state(directory: Path, server_wait_seconds: float = 0) -> None:
    """Start or stop the Nightshift worker to match its configured mode/schedule.

    Changes nothing if the current running state is already correct. Used after `mode`/
    `schedule` changes that configuration, instead of unconditionally restarting the worker:
    the container itself has no notion of its own schedule at all (only systemd's timers do - see
    DOCKER_COMPOSE_SERVER_NIGHTSHIFT_ENVS, which never passes DF_NIGHTSHIFT_START/STOP into the
    container), so a config change alone never requires touching it. Blindly restarting an
    already-correctly-running worker would interrupt whatever task it's mid-processing for
    nothing, since it doesn't handle a stop signal gracefully (an interrupted task simply starts
    over next run).

    The worker is only ever started while this install's `server` is running - a lone worker
    without its stack would just crash-loop, and a timer firing on a stack that was stopped on
    purpose must not start it. A skipped start is picked up by the next `server start`, which
    honors the schedule itself. Stopping the worker is always safe.

    `server_wait_seconds` lets the scheduled run wait for `server` to come up first: right after
    boot, Docker answers before its restart policy has brought the stack back, and a single check
    would skip the start for the whole night. A stack stopped on purpose only costs that one wait.

    A no-op on an install created before Nightshift existed (no `nightshift` service in its
    compose file). A `docker compose ps` failure stops the command instead of being read as "not
    running" - the state decides whether the worker gets started or stopped.
    """
    if not has_nightshift_service(directory):
        return
    should_be_up = _nightshift_should_be_up(directory)
    running = service_running_or_exit("nightshift", directory)
    if should_be_up and not running:
        if not wait_for_service_running("server", directory, server_wait_seconds):
            echo.info("The server isn't running - not starting the Nightshift worker.")
            return
        echo.info("Starting the Nightshift worker to match its current schedule.")
        start_nightshift(directory)
    elif not should_be_up and running:
        echo.info("Stopping the Nightshift worker - outside its configured shift-mode hours.")
        stop_nightshift(directory)


def start_server(directory: Path) -> None:
    """Ensure network and start server.

    In shift mode, outside Nightshift's configured hours, the worker is kept at zero replicas
    (`--scale nightshift=0`) instead of being started and then stopped back down - the systemd
    timer takes over from its next scheduled transition onward.
    """
    ensure_network(get_docker_network(directory))
    cmd = ["docker", "compose", "up", "-d", "--wait", "--remove-orphans"]
    if _nightshift_should_stay_down(directory):
        echo.info("Nightshift is in shift mode and outside its scheduled hours - leaving the worker stopped.")
        cmd.extend(["--scale", "nightshift=0"])
    try:
        run(cmd, cwd=directory, raises=DockerError)
    except DockerError as exc:
        _handle_start_failure(directory, exc)


def _handle_start_failure(directory: Path, exc: DockerError) -> NoReturn:
    """Report why the server stack failed to start, detecting a known Mongo credential mismatch.

    A stale ``mongo`` Docker volume from a previous install can hold root credentials that no
    longer match the current ``.env`` (e.g. after ``server uninstall``, which removes ``.env`` but
    not the volume, followed by a fresh ``server install``). That specific case surfaces as a
    generic "container server is unhealthy" from ``docker compose up`` with no indication of the
    real cause, so it's worth grepping the server logs for the underlying pymongo auth error.

    Always exits: ``--debug`` re-raises ``exc`` with its traceback, otherwise ``typer.Exit(1)``.
    """
    try:
        logs = run(
            ["docker", "compose", "logs", "--tail", "200", "server"],
            cwd=directory,
            capture_output=True,
            raises=DockerError,
        )
    except DockerError as logs_exc:
        echo.debug(logs_exc)
        logs = None

    if logs and all(signature in logs for signature in MONGO_AUTH_FAILURE_SIGNATURES):
        volume_name = resolve_compose_volume_name(directory, "mongo")
        if volume_name and volume_exists(volume_name):
            # Only blame the locally-managed volume once we've confirmed it actually exists -
            # a custom/external MongoDB (--mongodb-url) has no such volume at all, and a
            # confidently-worded `docker volume rm` suggestion for a volume that was never
            # created would be actively misleading.
            echo.error(
                f"DeepFellow Server failed to authenticate against MongoDB. The 'mongo' Docker volume "
                f"('{volume_name}') likely already holds credentials that no longer match .env (e.g. "
                "after 'server uninstall' followed by a fresh 'server install'). Restore the original "
                f"Mongo credentials in .env, or remove it with `docker volume rm {volume_name}`, then "
                "retry."
            )
        else:
            echo.error(
                "DeepFellow Server failed to authenticate against MongoDB. Check the DF_MONGO_* "
                "credentials in .env against the MongoDB instance they connect to."
            )
    elif not exc.args or exc.args[0] in (None, ""):
        # docker compose up's own output streams straight to the terminal (never captured), so
        # a plain DockerError from it carries no stderr of its own to show here.
        echo.error("Failed to start DeepFellow Server. See the Docker output above for details.")
    else:
        echo.error(f"Failed to start DeepFellow Server: {exc}")
    reraise_if_debug(exc)


def stop_server(directory: Path) -> None:
    """Stop server."""
    run(["docker", "compose", "stop", "server"], cwd=directory)


def start_nightshift(directory: Path) -> None:
    """Start only the Nightshift worker container.

    Uses `docker compose up -d`, not `docker compose start`/`docker start` - the latter two only
    operate on an already-existing container object and fail if it was removed (e.g. by `server
    stop`, which runs `docker compose down`), while `up` recreates it from `compose.yaml` if
    needed. Scoped strictly to the `nightshift` service: `--no-deps` keeps `up` from also starting
    (or recreating) the services it `depends_on` - rabbitmq, mongo, the vector DB, falkordb. Those
    belong to `server start`/`stop`, not to commands that manipulate the worker.
    """
    ensure_network(get_docker_network(directory))
    run(["docker", "compose", "up", "-d", "--no-deps", "nightshift"], cwd=directory)


def stop_nightshift(directory: Path) -> None:
    """Stop only the Nightshift worker container; its dependencies keep running."""
    run(["docker", "compose", "stop", "nightshift"], cwd=directory)


def restart_nightshift(directory: Path) -> None:
    """Restart only the Nightshift worker container - never its dependencies."""
    stop_nightshift(directory)
    start_nightshift(directory)


def print_nightshift_status(directory: Path) -> None:
    """Print the Nightshift worker's configured mode/schedule and live container state.

    Shared by `server nightshift status` and `server status` (which shows it alongside the
    server's own status), so the two never drift into two different renderings of the same info.
    """
    if not has_nightshift_service(directory):
        echo.info("nightshift status: not installed (run `deepfellow server install` to add it)")
        return
    env_content = read_env_file_to_dict(directory / ".env")
    mode = str(env_content.get("df_nightshift_mode", NightshiftModeChoice.always.value))
    running = is_service_running("nightshift", cwd=directory)
    current_word = "up" if running else "down"

    if mode == NightshiftModeChoice.shift.value:
        start = env_content.get("df_nightshift_start", "?")
        stop = env_content.get("df_nightshift_stop", "?")
        echo.info(f"nightshift mode: shift (start {start}, stop {stop})")
    else:
        echo.info(f"nightshift mode: {mode}")
    echo.info(f"nightshift status: {current_word}")

    # Only when actually running - docker stats/ps have nothing to report on a stopped or
    # removed container (is_service_running() already told us that above), and print_docker_status()
    # doesn't handle that gracefully - it prints a cascade of confusing errors instead.
    if running:
        print_docker_status(directory, "nightshift")
