# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Systemd unit management for the Nightshift worker's shift schedule.

User-level (`systemctl --user`) units, not system-level: matches df-cli's existing posture that
normal operation never requires root (root only ever appears as a rare, explicitly-confirmed
recovery fallback - see `deepfellow.common.system.rmtree()`). A system-level unit would need sudo
for every schedule change, permanently.

`.env` (`DF_NIGHTSHIFT_MODE`/`DF_NIGHTSHIFT_START`/`DF_NIGHTSHIFT_STOP`) stays the single source of
truth for the configured schedule - everything generated here is a disposable artifact derived
from it, never read back as authoritative. Two independent timer+service pairs are used (one to
start the worker, one to stop it) rather than a single pair, since a systemd timer only supports
one scheduled action per unit.
"""

import getpass
import os
import shlex
import shutil
import sys
from pathlib import Path

import typer

from deepfellow.common.defaults import NightshiftModeChoice
from deepfellow.common.echo import echo
from deepfellow.common.state import state
from deepfellow.common.system import is_command_available, run


def _config_home() -> Path:
    """The XDG config directory systemd looks in for user units (`$XDG_CONFIG_HOME`, else `~/.config`).

    Per the XDG spec a relative `$XDG_CONFIG_HOME` is invalid and ignored.
    """
    configured = Path(os.environ.get("XDG_CONFIG_HOME", ""))
    return configured if configured.is_absolute() else Path.home() / ".config"


SYSTEMD_USER_UNIT_DIR = _config_home() / "systemd" / "user"
SYSTEMD_RUNTIME_DIR = Path("/run/systemd/system")  # exists only on a host booted with systemd (see sd_booted(3))

START_UNIT_NAME = "nightshift-start"
STOP_UNIT_NAME = "nightshift-stop"
_UNIT_NAMES = (START_UNIT_NAME, STOP_UNIT_NAME)
SERVICE_TIMEOUT_SECONDS = 480  # a bit above `server nightshift reconcile`'s own 300s Docker + 120s server waits


class SystemdUserError(Exception):
    """`systemctl --user` couldn't reach the systemd user manager."""


class SudoLingerError(Exception):
    """Raised when a `loginctl` linger command fails, with or without sudo."""


def is_systemd_available() -> bool:
    """Whether this host was booted with systemd - shift mode's only real host requirement.

    `systemctl` on PATH isn't enough: WSL2 without systemd and containers ship the binary with no
    running systemd behind it, so the runtime directory `sd_booted()` itself checks must exist too.

    Used both to filter `shift` out of the install-time mode prompt on a host that could never
    support it, and by `assert_systemd_available()` to hard-block a `--nightshift-mode shift`
    flag or a `server nightshift mode`/`schedule` call on the same host.
    """
    return is_command_available("systemctl") and SYSTEMD_RUNTIME_DIR.is_dir()


def is_user_manager_reachable() -> bool:
    """Whether `systemctl --user` can talk to this session's systemd user manager."""
    try:
        run(["systemctl", "--user", "show-environment"], raises=SystemdUserError, quiet=True)
    except SystemdUserError:
        return False
    return True


def assert_systemd_available() -> None:
    """Exit with a clear error if shift mode's timers can't be managed from this session.

    Shift mode (and anything that manages its timers) is Linux/systemd-only; `always` mode never
    calls this and remains available everywhere Docker is. Matches the rest of the codebase's
    `assert_*` convention (e.g. `deepfellow.common.install.assert_docker`) - echo + `typer.Exit(1)`,
    not a custom exception type a caller would have to remember to catch.
    """
    if not is_systemd_available():
        # Purely factual, no "use X instead" - this fires from three different contexts
        # (the install-time mode prompt, `mode`, `schedule`), and only the first is a
        # live choice between two options; in the other two, the caller already issued a
        # specific command, so prescribing an alternative reads as presumptuous rather than
        # informative. The requested change never gets applied either way (this runs before any
        # .env write), so nothing needs to be undone.
        echo.error(
            "Shift mode requires systemd, which isn't running on this host (`systemctl` is missing or the host "
            "wasn't booted with systemd - e.g. a container or WSL2 without systemd). It's only available on "
            "Linux hosts running systemd."
        )
        raise typer.Exit(1)
    if not is_user_manager_reachable():
        echo.error(
            "Shift mode needs your systemd user session, which isn't reachable from this shell (typically after "
            "`su` or `sudo -u`). Log in as this user directly, e.g. over SSH or a console, and try again."
        )
        raise typer.Exit(1)


def _deepfellow_command() -> list[str]:
    """The command that runs this CLI, as an absolute invocation a systemd unit can use.

    systemd units don't inherit the user's shell PATH, so a bare `deepfellow` wouldn't resolve for
    a CLI installed into a virtualenv or via `uv tool`/`pipx`.
    """
    executable = shutil.which("deepfellow")
    return [executable] if executable else [sys.executable, "-m", "deepfellow.main"]


def _exec_start(command: list[str]) -> str:
    """Quote `command` for a unit's ExecStart= (systemd also expands `$` and `%`, so escape them)."""
    return " ".join(shlex.quote(part).replace("$", "$$").replace("%", "%%") for part in command)


def _oneshot_service_unit(description: str, working_directory: Path, exec_start: str) -> str:
    """A `Type=oneshot` unit: runs `exec_start` once (from `working_directory`) and exits.

    `TimeoutStartSec` leaves room for the command's own wait for the Docker daemon.
    """
    # systemd expands `%` specifiers in WorkingDirectory= too, not only in ExecStart=.
    escaped_directory = str(working_directory).replace("%", "%%")
    return (
        f"[Unit]\nDescription={description}\n\n"
        f"[Service]\nType=oneshot\nWorkingDirectory={escaped_directory}\nExecStart={exec_start}\n"
        f"TimeoutStartSec={SERVICE_TIMEOUT_SECONDS}\n"
    )


def _timer_unit(description: str, unit_name: str, on_calendar: str) -> str:
    """A timer that fires `{unit_name}.service` at `on_calendar`.

    `Persistent=true` so a missed trigger (host was off) fires once at the next boot instead of
    silently being skipped.
    """
    return (
        f"[Unit]\nDescription={description}\n\n"
        f"[Timer]\nOnCalendar={on_calendar}\nPersistent=true\nUnit={unit_name}.service\n\n"
        "[Install]\nWantedBy=timers.target\n"
    )


def generate_nightshift_units(directory: Path, start: str, stop: str) -> dict[str, str]:
    """Build the four unit files (start/stop x service/timer) for shift-mode scheduling.

    Both services run the same `server nightshift reconcile` command: it compares the current time
    with the configured window and starts or stops the worker only if its state is wrong. A timer
    that blindly started or stopped on its trigger could, once `Persistent=true` replays both
    missed triggers after downtime, fire in the wrong order and leave the worker running outside
    its window.

    Args:
        directory: The server install directory (`compose.yaml`/`.env` live here).
        start: Start hour, "HH:MM".
        stop: Stop hour, "HH:MM".
    """
    reconcile = _exec_start(
        [*_deepfellow_command(), "server", "nightshift", "reconcile", "--directory", str(directory)]
    )
    start_hour, start_minute = start.split(":")
    stop_hour, stop_minute = stop.split(":")
    return {
        f"{START_UNIT_NAME}.service": _oneshot_service_unit(
            "Reconcile the DeepFellow Nightshift worker at its start hour", directory, reconcile
        ),
        f"{START_UNIT_NAME}.timer": _timer_unit(
            "Start the DeepFellow Nightshift worker on schedule",
            START_UNIT_NAME,
            f"*-*-* {start_hour}:{start_minute}:00",
        ),
        f"{STOP_UNIT_NAME}.service": _oneshot_service_unit(
            "Reconcile the DeepFellow Nightshift worker at its stop hour", directory, reconcile
        ),
        f"{STOP_UNIT_NAME}.timer": _timer_unit(
            "Stop the DeepFellow Nightshift worker on schedule",
            STOP_UNIT_NAME,
            f"*-*-* {stop_hour}:{stop_minute}:00",
        ),
    }


def install_nightshift_timers(directory: Path, start: str, stop: str) -> None:
    """Write the shift-mode unit files and enable+start their timers.

    Idempotent: safe to call again (e.g. after a `schedule` change) - overwrites the unit files with
    freshly generated content and reloads/re-enables them.
    """
    assert_systemd_available()
    SYSTEMD_USER_UNIT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, content in generate_nightshift_units(directory, start, stop).items():
        (SYSTEMD_USER_UNIT_DIR / filename).write_text(content)
    run(["systemctl", "--user", "daemon-reload"])
    for unit_name in _UNIT_NAMES:
        run(["systemctl", "--user", "enable", "--now", f"{unit_name}.timer"])


def _units_owned_by_another_install(directory: Path) -> Path | None:
    """The other install directory the existing unit files belong to, or None if they're not foreign.

    The unit names are global, so after moving to a new `--directory` the live timers belong to the
    new install. Removing them on behalf of the old one (`uninstall`/`prune`/`mode always`) would
    silently stop the live install's schedule. Ownership is read from each service's
    `WorkingDirectory=`; units with no readable owner (e.g. a stray timer file) count as ours.
    """
    for name in _UNIT_NAMES:
        service = SYSTEMD_USER_UNIT_DIR / f"{name}.service"
        if not service.is_file():
            continue
        for line in service.read_text().splitlines():
            if line.startswith("WorkingDirectory="):
                owner = Path(line.removeprefix("WorkingDirectory=").replace("%%", "%"))
                if owner.resolve() != directory.resolve():
                    return owner
    return None


def remove_nightshift_timers(directory: Path) -> None:
    """Disable and delete the shift-mode unit files of the install in `directory`, if present.

    A no-op when Nightshift was never in shift mode (e.g. called unconditionally from
    `uninstall`/`prune`, which don't otherwise know the configured mode), when `systemctl` itself
    isn't available (a non-systemd host can't have installed these units in the first place), and
    when the units belong to a different install directory.
    """
    if not is_command_available("systemctl"):
        return
    suffixes = (".timer", ".service")
    unit_files = (SYSTEMD_USER_UNIT_DIR / f"{name}{suffix}" for name in _UNIT_NAMES for suffix in suffixes)
    if not any(path.exists() for path in unit_files):
        return
    if (owner := _units_owned_by_another_install(directory)) is not None:
        echo.info(f"Leaving the Nightshift systemd timers alone - they belong to the install in {owner}.")
        return
    for unit_name in _UNIT_NAMES:
        run(["systemctl", "--user", "disable", "--now", f"{unit_name}.timer"], check=False)
        (SYSTEMD_USER_UNIT_DIR / f"{unit_name}.service").unlink(missing_ok=True)
        (SYSTEMD_USER_UNIT_DIR / f"{unit_name}.timer").unlink(missing_ok=True)
    # Only makes systemd forget the deleted units - the files are already gone, so a failure here (e.g. an
    # unreachable user manager) must not abort `uninstall`/`prune` before they remove the directory.
    try:
        run(["systemctl", "--user", "daemon-reload"], raises=SystemdUserError, quiet=True)
    except SystemdUserError as exc:
        echo.warning(f"Could not reload the systemd user manager ({exc}); run `systemctl --user daemon-reload`.")


def _linger_enabled(username: str) -> bool:
    """Whether lingering is already enabled for `username` (readable without any privileges)."""
    try:
        output = run(
            ["loginctl", "show-user", username, "--property=Linger", "--value"],
            raises=SudoLingerError,
            capture_output=True,
        )
    except SudoLingerError:
        return False
    return (output or "").strip() == "yes"


def ensure_linger_enabled() -> None:
    """One-time step so the user-level systemd instance survives reboot without a login session.

    Does nothing if lingering is already on (checked first, so calling this again - e.g. from
    `apply()` after `resolve()` already did it - can never prompt). Whether enabling it needs root
    depends on session context (SSH/automation vs. a local login - a known, open systemd/polkit
    inconsistency, not a distro difference - see design.md), so this doesn't try to detect it: it
    attempts the plain command first and only then offers sudo. `sudo` asks for the password itself
    on the terminal, so this process never sees it; under `--non-interactive` it is run with `-n`
    instead, so it fails fast rather than prompting.
    """
    username = getpass.getuser()

    if _linger_enabled(username):
        return

    try:
        run(["loginctl", "enable-linger", username], raises=SudoLingerError, quiet=True)
    except SudoLingerError:
        pass
    else:
        return

    echo.warning(
        "Enabling Nightshift to run unattended (survive reboot without a login session) needs "
        f"elevated privileges on this host: `loginctl enable-linger {username}`."
    )
    if echo.confirm("Retry with sudo?", default=True):
        sudo = ["sudo", "-n"] if state.non_interactive else ["sudo"]
        try:
            run([*sudo, "loginctl", "enable-linger", username], raises=SudoLingerError, quiet=True)
        except SudoLingerError:
            echo.error(f"sudo loginctl enable-linger failed. Run manually: sudo loginctl enable-linger {username}")
            raise typer.Exit(1) from None
    else:
        echo.error(f"Run manually: sudo loginctl enable-linger {username}")
        raise typer.Exit(1)


def reconcile_nightshift_schedule(directory: Path, mode: str, start: str, stop: str) -> None:
    """Make the systemd timers match the desired Nightshift mode/schedule.

    The single place that decides "shift -> ensure linger + install timers, else -> remove any
    existing timers" - shared by `apply()` (so choosing `shift` mode at install time actually
    creates working timers, not just `.env` fields) and the `server nightshift mode`/`schedule`
    commands, so mode/schedule reconciliation never has two different implementations to drift
    apart. Idempotent either way - safe to call again (e.g. on a self-healing repair, or when
    `schedule` only changed the hours and the mode was already `shift`).
    """
    if mode == NightshiftModeChoice.shift.value:
        # First thing, before anything else - ensure_linger_enabled() would otherwise attempt a
        # `loginctl` call that doesn't even exist as a binary on a non-systemd host (e.g. macOS),
        # limping through a confusing sudo retry dance before failing for the wrong reason.
        assert_systemd_available()
        ensure_linger_enabled()
        install_nightshift_timers(directory, start, stop)
    else:
        remove_nightshift_timers(directory)
