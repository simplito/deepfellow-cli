# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Offering and adding RabbitMQ and the Nightshift worker on `server update` for installs without them."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import typer

from deepfellow.common.config import read_env_file_to_dict, save_env_file
from deepfellow.common.defaults import (
    DEFAULT_NIGHTSHIFT_MODE,
    DF_RABBITMQ_URL,
    DOCKER_COMPOSE_CONFIG_FILENAME,
    DOCKER_COMPOSE_SERVER_RABBITMQ_ENVS,
    NIGHTSHIFT_FEATURES,
    NightshiftModeChoice,
)
from deepfellow.common.docker import load_compose_file, save_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.state import state
from deepfellow.server.utils.configure import (
    NightshiftConfig,
    external_rabbitmq_envs,
    is_custom_rabbitmq,
    local_rabbitmq_envs,
)
from deepfellow.server.utils.docker import has_nightshift_service
from deepfellow.server.utils.install import build_nightshift_service
from deepfellow.server.utils.nightshift import SHIFT_WITHOUT_HOURS_WARNING, validate_nightshift_schedule
from deepfellow.server.utils.systemd import (
    ensure_linger_enabled,
    is_systemd_available,
    is_user_manager_reachable,
    reconcile_nightshift_schedule,
    remove_nightshift_timers,
)


def format_nightshift_features() -> str:
    """Return the features that don't work without Nightshift and RabbitMQ, one bullet per line."""
    return "\n".join(f"  - {feature}" for feature in NIGHTSHIFT_FEATURES)


def warn_nightshift_declined() -> None:
    """Warn that the update went on without Nightshift, and how to add it later."""
    echo.warning(
        "Nightshift and RabbitMQ were not added, so these features don't work:\n"
        f"{format_nightshift_features()}\n"
        "Run `deepfellow server update --nightshift` to add them (with `--rabbitmq-url host:port` for an existing "
        "RabbitMQ), or `deepfellow server install`."
    )


def _missing_nightshift_message() -> str:
    """Explain that this install lacks Nightshift and RabbitMQ, and what doesn't work without them."""
    return (
        "This DeepFellow Server version processes background jobs through the Nightshift worker and RabbitMQ, "
        f"which this install doesn't have. Without them these features don't work:\n{format_nightshift_features()}"
    )


def _should_add(
    nightshift: bool | None, rabbitmq_url: str | None, rabbitmq_username: str, rabbitmq_password: str
) -> bool:
    """Decide whether to add Nightshift and RabbitMQ - from the options, `--yes`, or by asking.

    Any `--rabbitmq-*` option implies `--nightshift`.

    Raises:
        typer.Exit: In non-interactive mode without `--yes` and without a Nightshift option.
    """
    if nightshift is not None:
        return nightshift
    if rabbitmq_url is not None or rabbitmq_username or rabbitmq_password or state.yes:
        return True
    if state.non_interactive:
        echo.error(
            f"{_missing_nightshift_message()}\n"
            "Run `deepfellow server update` with `--nightshift` (the RabbitMQ in .env, otherwise a local one), "
            "`--rabbitmq-url host:port` with "
            "`--rabbitmq-username`/`--rabbitmq-password` (existing RabbitMQ), or `--no-nightshift` (skip)."
        )
        raise typer.Exit(1)
    return echo.confirm(
        f"{_missing_nightshift_message()}\nAdd Nightshift and RabbitMQ?",
        default=True,
    )


def _resolve_rabbitmq(
    nightshift: bool | None,
    rabbitmq_url: str | None,
    rabbitmq_username: str,
    rabbitmq_password: str,
    original_env: dict[str, Any],
) -> NightshiftConfig:
    """Choose the RabbitMQ to add: from `--rabbitmq-url`, then `.env`, then `--nightshift`/`--yes`, then by asking.

    An external RabbitMQ taken from `.env` is announced, since it wins over `--nightshift`/`--yes`.
    """
    env_url = str(original_env.get("df_rabbitmq_url") or "") or None
    url = rabbitmq_url if rabbitmq_url is not None else env_url
    if url is not None:
        if url == DF_RABBITMQ_URL:
            return local_rabbitmq_envs(rabbitmq_username, rabbitmq_password, original_env)
        if rabbitmq_url is None:
            echo.warning(
                f"Using the RabbitMQ at {url} from .env. To use another one, pass `--rabbitmq-url host:port` "
                f"(`--rabbitmq-url {DF_RABBITMQ_URL}` for a local one)."
            )
            # Taken from `.env` as a whole, so its credentials aren't asked for again.
            rabbitmq_username = rabbitmq_username or str(original_env.get("df_rabbitmq_user") or "")
            rabbitmq_password = rabbitmq_password or str(original_env.get("df_rabbitmq_password") or "")
        return external_rabbitmq_envs(url, rabbitmq_username, rabbitmq_password, original_env)

    if nightshift or state.yes or not is_custom_rabbitmq(DF_RABBITMQ_URL):
        return local_rabbitmq_envs(rabbitmq_username, rabbitmq_password, original_env)
    return external_rabbitmq_envs(DF_RABBITMQ_URL, rabbitmq_username, rabbitmq_password, original_env)


def _resolve_mode(original_env: dict[str, Any]) -> dict[str, str]:
    """Keep a valid Nightshift mode/schedule from `.env`, otherwise fall back to `always`.

    For a kept `shift` schedule with both hours, linger is enabled here rather than when writing
    files: like in `server install`, it may prompt for sudo, which must happen before any change.
    """
    always = {"DF_NIGHTSHIFT_MODE": NightshiftModeChoice.always.value}
    mode = original_env.get("df_nightshift_mode")
    if not mode:
        return always

    mode = str(mode)
    start = str(original_env.get("df_nightshift_start") or "")
    stop = str(original_env.get("df_nightshift_stop") or "")
    try:
        validate_nightshift_schedule(mode, start, stop)
    except typer.BadParameter as exc:
        echo.warning(f"Ignoring the Nightshift schedule in .env ({exc.message}) - Nightshift will run always.")
        return always

    if mode != NightshiftModeChoice.shift.value:
        return {"DF_NIGHTSHIFT_MODE": mode}
    if not is_systemd_available():
        echo.warning("Shift mode in .env needs systemd, which this host doesn't have - Nightshift will run always.")
        return always
    if start and stop:
        # Checked now, as the timers are only installed after `.env` is written.
        if not is_user_manager_reachable():
            echo.warning(
                "Shift mode in .env needs your systemd user session, which isn't reachable from this shell "
                "(typically after `su` or `sudo -u`) - Nightshift will run always. Log in as this user directly "
                "and run `deepfellow server nightshift mode shift` to schedule it again."
            )
            return always
        ensure_linger_enabled()
    return {"DF_NIGHTSHIFT_MODE": mode, "DF_NIGHTSHIFT_START": start, "DF_NIGHTSHIFT_STOP": stop}


def resolve_nightshift_addition(
    directory: Path,
    nightshift: bool | None,
    rabbitmq_url: str | None,
    rabbitmq_username: str,
    rabbitmq_password: str,
) -> NightshiftConfig | None:
    """Decide whether and how `server update` adds RabbitMQ and Nightshift, before anything is written.

    Every prompt and validation happens here, so declining, aborting or a bad option never leaves
    a half-changed install behind.

    Args:
        directory: The server install directory.
        nightshift: `--nightshift` (True), `--no-nightshift` (False) or neither (None).
        rabbitmq_url: `--rabbitmq-url`, None when not given.
        rabbitmq_username: `--rabbitmq-username`, empty when not given.
        rabbitmq_password: `--rabbitmq-password`, empty when not given.

    Returns:
        The `.env` values and compose services to add, or None when nothing is added (Nightshift
        is already installed, or adding it was declined).

    Raises:
        typer.BadParameter: `--no-nightshift` combined with a `--rabbitmq-*` option.
        typer.Exit: In non-interactive mode without `--yes` and without a Nightshift option.
    """
    if nightshift is False and (rabbitmq_url is not None or rabbitmq_username or rabbitmq_password):
        raise typer.BadParameter("`--no-nightshift` can't be combined with the `--rabbitmq-*` options.")
    if has_nightshift_service(directory):
        return None
    if not _should_add(nightshift, rabbitmq_url, rabbitmq_username, rabbitmq_password):
        return None

    original_env = read_env_file_to_dict(directory / ".env")
    rabbitmq = _resolve_rabbitmq(nightshift, rabbitmq_url, rabbitmq_username, rabbitmq_password, original_env)
    return NightshiftConfig(envs=_resolve_mode(original_env) | rabbitmq.envs, docker_compose=rabbitmq.docker_compose)


def add_nightshift_to_install(directory: Path, config: NightshiftConfig) -> None:
    """Add RabbitMQ and Nightshift, as resolved by `resolve_nightshift_addition`, to an install. No prompts.

    Only adds: existing services, env entries and `.env` values other than the resolved ones stay as they are.

    Args:
        directory: The server install directory.
        config: The resolved `.env` values, plus the `rabbitmq` service when RabbitMQ is local.
    """
    save_env_file(directory / ".env", config.envs, quiet=True)

    mode = config.envs.get("DF_NIGHTSHIFT_MODE", DEFAULT_NIGHTSHIFT_MODE)
    start = config.envs.get("DF_NIGHTSHIFT_START", "")
    stop = config.envs.get("DF_NIGHTSHIFT_STOP", "")
    if mode == NightshiftModeChoice.shift.value and not (start and stop):
        remove_nightshift_timers(directory)
        echo.warning(SHIFT_WITHOUT_HOURS_WARNING)
    else:
        reconcile_nightshift_schedule(directory, mode, start, stop)

    # Written last: until `nightshift` is in compose.yaml, the next `server update` offers to add it
    # again, so a failure above doesn't leave an install that looks complete but has no timers.
    compose_file = directory / DOCKER_COMPOSE_CONFIG_FILENAME
    compose = load_compose_file(compose_file)
    services = compose["services"]
    server = services["server"]
    environment = server.setdefault("environment", [])
    environment.extend(env for env in DOCKER_COMPOSE_SERVER_RABBITMQ_ENVS if env not in environment)
    is_local_rabbitmq = bool(config.docker_compose)
    if is_local_rabbitmq:
        rabbitmq = deepcopy(config.docker_compose["rabbitmq"])
        if "networks" in server:
            rabbitmq["networks"] = deepcopy(server["networks"])
        services["rabbitmq"] = rabbitmq
        compose.setdefault("volumes", {})["rabbitmq_data"] = None
        server.setdefault("depends_on", {})["rabbitmq"] = {"condition": "service_healthy"}
    services["nightshift"] = build_nightshift_service(server)
    save_compose_file(compose, compose_file)

    rabbitmq_description = (
        "a local RabbitMQ" if is_local_rabbitmq else f"the RabbitMQ at {config.envs['DF_RABBITMQ_URL']}"
    )
    echo.success(f"Added the Nightshift worker using {rabbitmq_description} to this install.")
    echo.info(
        "To change the RabbitMQ connection later, use `deepfellow server config set` or `deepfellow server install`."
    )
