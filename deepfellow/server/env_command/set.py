# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""server env set command."""

from pathlib import Path

import httpx
import typer

from deepfellow.common.config import dict_to_env, read_env_file, read_env_file_to_dict
from deepfellow.common.defaults import DOCKER_COMPOSE_CONFIG_FILENAME, NightshiftModeChoice
from deepfellow.common.docker import is_service_running, load_compose_file, local_url
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get, env_set
from deepfellow.common.install import assert_docker
from deepfellow.common.state import state
from deepfellow.common.validation import validate_bind_address, validate_hhmm
from deepfellow.server.utils.docker import start_server, stop_server
from deepfellow.server.utils.nightshift import apply_nightshift_schedule
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.storage import config_json_exists
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()

# The systemd timers are derived from these - changing any of them has to regenerate the timers too.
_NIGHTSHIFT_SCHEDULE_KEYS = frozenset({"DF_NIGHTSHIFT_MODE", "DF_NIGHTSHIFT_START", "DF_NIGHTSHIFT_STOP"})
# Docker Compose rejects a host name here and the CLI builds its URLs from these, so they are validated
# (and IPv6 bracketed) like `--bind-address` at install, instead of failing at the next restart.
_BIND_ADDRESS_KEYS = frozenset({"DF_SERVER_BIND_ADDRESS", "DF_INTERNAL_BIND_ADDRESS"})


def _retarget_stored_server_url(directory: Path, old_bind_address: str | None, new_bind_address: str) -> None:
    """Point the CLI's stored Server URL at a new bind address, unless the user set it to something else.

    `server login` and `suite install` store `DF_SERVER_URL` as the URL derived from the bind address, and
    every command that calls the Server API reads it back, so a bind address changed later would leave
    them calling the old one.

    Args:
        directory: Server install directory.
        old_bind_address: Bind address in `.env` before the change; `None` if it was unset.
        new_bind_address: Validated bind address being written.
    """
    port = env_get(directory / ".env", "DF_SERVER_PORT", should_raise=False)
    if not port:
        return
    old_url = local_url(port, old_bind_address)
    new_url = local_url(port, new_bind_address)
    stored_url = state.cli_config.get("df_server_url")
    if old_url == new_url or not stored_url:
        return
    if stored_url == old_url:
        env_set(state.cli_config_file, "DF_SERVER_URL", new_url, should_raise=False, docker_note=False)
    else:
        echo.warning(
            f"The stored Server URL ({stored_url}) differs from the one derived from the previous bind address "
            f"({old_url}), so I left it alone. Set it to {new_url} if it should follow the new bind address."
        )


# Broker settings the server keeps in the `rabbitmq` section of config.json once it has started.
_RABBITMQ_ENV_FIELDS = {
    "DF_RABBITMQ_URL": "host and port",
    "DF_RABBITMQ_USER": "username",
    "DF_RABBITMQ_PASSWORD": "password",
}
_RABBITMQ_CONFIG_EXAMPLE = {
    "DF_RABBITMQ_URL": '\'rabbitmq={"host": "<host>", "port": <port>}\'',
    "DF_RABBITMQ_USER": '\'rabbitmq={"username": "<user>"}\'',
    "DF_RABBITMQ_PASSWORD": '\'rabbitmq={"password": "<password>"}\'',
}


def _resolved_env_name(env_name: str, df_prefix: bool) -> str:
    """Return the env var name exactly as `env_set` will write it, for comparison against config.json fields."""
    env_name = env_name.upper()
    if df_prefix and not env_name.startswith("DF_"):
        env_name = f"DF_{env_name}"
    return env_name


def _set_nightshift_schedule_key(directory: Path, name: str, value: str) -> None:
    """Write one Nightshift mode/schedule key and keep the timers and the worker in line with it.

    Deliberately unopinionated: no hours are invented for shift mode without them (the admin gets a
    warning about the consequence), and no server restart is offered - these keys never reach the
    containers, `start_server()` reads them from `.env` itself.
    """
    # The hours are only validated as part of a shift schedule, so a bad value written while the
    # mode is `always` would otherwise land in `.env` unchecked and surface at the next `mode shift`.
    if name != "DF_NIGHTSHIFT_MODE" and value:
        validate_hhmm(value)
    stored = read_env_file_to_dict(directory / ".env")
    values = {
        "DF_NIGHTSHIFT_MODE": str(stored.get("df_nightshift_mode") or NightshiftModeChoice.always.value),
        "DF_NIGHTSHIFT_START": str(stored.get("df_nightshift_start") or ""),
        "DF_NIGHTSHIFT_STOP": str(stored.get("df_nightshift_stop") or ""),
    }
    values[name] = value
    apply_nightshift_schedule(
        directory,
        values["DF_NIGHTSHIFT_MODE"],
        values["DF_NIGHTSHIFT_START"],
        values["DF_NIGHTSHIFT_STOP"],
        {name: value},
    )
    echo.success(f"{name} set to '{value}'.")


def _dynamic_field_name(directory: Path, env_name: str) -> str | None:
    """Return the config.json field name if `env_name` is dynamic config on the running instance.

    The server only seeds config.json from `.env` the first time it starts; once config.json
    exists, the running instance never reads `.env` again for those fields, so setting one via
    `.env` and restarting silently has no effect. Only checked while the server is already
    running — before the first start, `.env` is still the real seed for config.json, so writing
    it is correct.

    Best-effort: if the server isn't running, no user token is stored locally, or the admin API
    can't be reached, returns None so the caller falls back to the plain `.env` write.
    """
    if not is_service_running("server", cwd=directory):
        return None

    port = env_get(directory / ".env", "DF_SERVER_PORT", should_raise=False)
    if not port:
        return None

    secrets_file = state.cli_secrets_file
    token = read_env_file(secrets_file).get("DF_USER_TOKEN") if secrets_file.is_file() else None
    if not token:
        return None

    bind_address = env_get(directory / ".env", "DF_SERVER_BIND_ADDRESS", should_raise=False)
    try:
        response = httpx.get(
            f"{local_url(port, bind_address)}/admin/config",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        response.raise_for_status()
        config = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        echo.warning(
            f"Could not check /admin/config ({exc}). If {env_name} is dynamic configuration, "
            "writing it to .env will have no effect."
        )
        return None

    if env_name in _RABBITMQ_ENV_FIELDS and isinstance(config.get("rabbitmq"), dict):
        return "rabbitmq"

    dynamic_envs = dict_to_env(config)
    if env_name not in dynamic_envs:
        return None

    return env_name.removeprefix("DF_").lower()


def _has_local_rabbitmq(directory: Path) -> bool:
    """Check whether the install runs its own RabbitMQ container."""
    compose = load_compose_file(directory / DOCKER_COMPOSE_CONFIG_FILENAME)
    return "rabbitmq" in (compose.get("services") or {})


@app.command()
def set(
    directory: Path = directory_option(),
    env_name: str = typer.Argument(..., help="Name of the environment variable", callback=lambda x: x.upper()),
    env_value: str = typer.Argument("", help="Value of the environment variable"),
    df_prefix: bool = typer.Option(True, help="Add DF_ prefix if not provided?"),
    no_restart: bool = typer.Option(False, "--no-restart", help="Skip restarting the server stack after the change."),
) -> None:
    """Set environment configuration."""
    check_server_directory(directory)
    assert_docker()

    resolved_name = _resolved_env_name(env_name, df_prefix)
    if resolved_name in _BIND_ADDRESS_KEYS:
        env_value = validate_bind_address(env_value) or ""
    if resolved_name in _NIGHTSHIFT_SCHEDULE_KEYS:
        _set_nightshift_schedule_key(directory, resolved_name, env_value)
        return

    field_name = _dynamic_field_name(directory, resolved_name)
    local_broker_credential = False
    if field_name == "rabbitmq":
        local_broker_credential = resolved_name != "DF_RABBITMQ_URL" and _has_local_rabbitmq(directory)
        if not local_broker_credential:
            echo.error(
                f"The RabbitMQ {_RABBITMQ_ENV_FIELDS[resolved_name]} is dynamic configuration stored in config.json: "
                f"{resolved_name} in .env is only the initial value, read on the server's first start, so changing "
                f"it now has no effect. Use `deepfellow server config set {_RABBITMQ_CONFIG_EXAMPLE[resolved_name]}` "
                "instead (applied without a restart)."
            )
            raise typer.Exit(1)
        field_name = None
    if field_name:
        echo.error(
            f"{resolved_name} is dynamic configuration stored in config.json. Writing it to .env has no effect "
            f"once the server is running. Use `deepfellow server config set {field_name}=<value>` instead."
        )
        raise typer.Exit(1)
    # Existence alone doesn't tell us whether this particular variable is one of the fields that
    # migrated to config.json - only the admin API knows that, and it's unreachable while the server
    # is down - so this warns rather than blocking the write.
    if not is_service_running("server", cwd=directory) and config_json_exists():
        echo.warning(
            "The server isn't running, so I can't check whether this variable is dynamic configuration stored "
            "in config.json. config.json already exists on this install, though — if it was migrated there, "
            "this write will have no effect once the server starts. Start the server and use "
            "`deepfellow server config set` if unsure."
        )

    old_bind_address = env_get(directory / ".env", "DF_SERVER_BIND_ADDRESS", should_raise=False)
    env_set(directory / ".env", env_name, env_value, df_prefix)
    if local_broker_credential:
        echo.warning(
            f"{resolved_name} configures the local RabbitMQ container, but the server connects with the "
            "credentials from config.json, so set the same value there too: "
            f"`deepfellow server config set {_RABBITMQ_CONFIG_EXAMPLE[resolved_name]}`. Also note that RabbitMQ "
            "applies these credentials only when it first initialises its data volume, so for an existing "
            "install the broker keeps its old user and password until you change them in RabbitMQ itself "
            "(`rabbitmqctl change_password`) or recreate the `rabbitmq_data` volume."
        )
    if resolved_name == "DF_SERVER_BIND_ADDRESS":
        _retarget_stored_server_url(directory, old_bind_address, env_value)
    if not no_restart and echo.confirm("Restart the server now to apply the change?", default=True):
        echo.info("Restarting the server...")
        stop_server(directory)
        start_server(directory)
        echo.success("Server restarted successfully.")
