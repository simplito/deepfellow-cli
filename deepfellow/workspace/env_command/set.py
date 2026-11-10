# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""workspace env set command."""

import re
from collections.abc import Callable, Mapping
from pathlib import Path

import typer

from deepfellow.common.defaults import WORKSPACE_MONGO_VOLUME
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import InstallError
from deepfellow.common.validation import (
    validate_bind_address,
    validate_email,
    validate_mongo_url,
    validate_origin,
    validate_password,
    validate_redis_url,
    validate_url,
)
from deepfellow.workspace.env_command.info import ENV_METADATA
from deepfellow.workspace.utils.docker import offer_restart
from deepfellow.workspace.utils.install import (
    BIND_ADDRESS_KEY,
    DOCKER_NETWORK_KEY,
    IMAGE_KEY,
    MONGO_KEY_KEY,
    MONGO_PASSWORD_KEY,
    PORT_KEY,
    build_env,
    current_service_images,
    read_installed_env,
    resolve_stack_settings,
    validate_env,
    write_stack,
)
from deepfellow.workspace.utils.options import directory_option
from deepfellow.workspace.utils.validation import (
    check_workspace_directory,
    validate_flag,
    validate_mcp_auth_token,
    validate_port_text,
)

app = typer.Typer()

# The names `read_env_file` accepts back, after upper-casing.
_KEY_NAME = re.compile(r"[A-Z_][A-Z0-9_]*")

# Changing one of these takes more than a new value in .env: the stored data depends on it, or a dedicated command
# does the change safely.
_PROTECTED_KEYS = {
    "APP_SECRET": "a new APP_SECRET signs all users out and makes the stored MCP credentials unreadable.",
    MONGO_PASSWORD_KEY: "Mongo keeps its own copy of the password in its data, so a new one in .env would stop "
    "Workspace from starting.",
    MONGO_KEY_KEY: "it secures the replica set of the Mongo installed with Workspace, and rotating it is not "
    "supported here.",
    IMAGE_KEY: "use 'workspace update' (with --tag or --image for a chosen version), which pulls the image before "
    "changing anything.",
}

# Stack settings an empty value would silently reset to the CLI's default, so they always need a value.
_NOT_REMOVABLE_KEYS = (PORT_KEY, DOCKER_NETWORK_KEY)

_VALIDATORS: dict[str, Callable[[str], str | None]] = {
    PORT_KEY: validate_port_text,
    "SMTP_PORT": validate_port_text,
    BIND_ADDRESS_KEY: validate_bind_address,
    "DF_SERVER_URL": validate_url,
    "PUBLIC_URL": validate_origin,
    "MONGO_DB_URL": validate_mongo_url,
    "REDIS_URL": validate_redis_url,
    "BOOTSTRAP_ADMIN_EMAIL": validate_email,
    "EMAIL_FROM_ADDRESS": validate_email,
    "BOOTSTRAP_ADMIN_PASSWORD": validate_password,
    "MCP_AUTH_TOKEN": validate_mcp_auth_token,
    "SMTP_SECURE": validate_flag,
    "TRUSTED_PROXY_ENABLED": validate_flag,
}


def _validated_value(key: str, value: str) -> str:
    """Check that `key` may be set and return `value` in the form to store.

    Args:
        key: The .env key.
        value: The value given; an empty one skips the key's validator and is handled by the caller.

    Returns:
        The value to store (e.g. an IPv6 bind address in brackets).

    Raises:
        InstallError: When the key name is invalid, the key is protected or the value is invalid.
    """
    if not _KEY_NAME.fullmatch(key):
        raise InstallError(
            f"{key!r} is not a valid setting name: use letters, digits and underscores, not starting with a digit."
        )
    if reason := _PROTECTED_KEYS.get(key):
        raise InstallError(f"{key} cannot be changed with 'workspace env set': {reason}")
    if "\n" in value or "\r" in value:
        raise InstallError(f"{key} must not contain a line break.")
    if not value and key in _NOT_REMOVABLE_KEYS:
        raise InstallError(f"{key} cannot be removed; give a value.")
    validator = _VALIDATORS.get(key)
    if not value or validator is None:
        return value
    try:
        return validator(value) or ""
    except typer.BadParameter as exc:
        raise InstallError(f"Invalid {key}: {exc.message}") from exc


def _new_env(existing: Mapping[str, str], key: str, value: str) -> dict[str, str]:
    """Build the .env content with `key` set to `value`, keeping the secrets and generating missing ones.

    An empty value removes the key, except for the bind address, where empty means all interfaces.

    Args:
        existing: The current .env.
        key: The .env key.
        value: The validated value.

    Returns:
        The new .env content.

    Raises:
        InstallError: When a stack setting is invalid or `MONGO_DB_NAME` is set without an external Mongo.
    """
    changed = {**existing, key: value}
    if not value and key != BIND_ADDRESS_KEY:
        # The app refuses an empty value for its own settings, so a cleared one is left out and the app uses its
        # default; build_env fills in the defaults the CLI owns (PUBLIC_URL, MCP_AUTH_TOKEN).
        del changed[key]
    _, port, _, _ = resolve_stack_settings(changed, None, None, None, None)
    # `passed` stops build_env from resetting an explicit PUBLIC_URL to the default form.
    env = build_env(changed, {key: value}, port)
    if key == "MONGO_DB_NAME" and value and not env.get("MONGO_DB_URL"):
        raise InstallError("MONGO_DB_NAME applies to an external MongoDB only; set MONGO_DB_URL first.")
    return env


def _warn_about_switches(existing: Mapping[str, str], env: Mapping[str, str]) -> None:
    """Warn when Mongo or Redis moved between the stack's own service and an external one.

    Args:
        existing: The .env before the change.
        env: The .env after the change.
    """
    was_local_mongo, is_local_mongo = not existing.get("MONGO_DB_URL"), not env.get("MONGO_DB_URL")
    if was_local_mongo and not is_local_mongo:
        echo.warning(
            "Workspace now uses the external MongoDB. Data is not moved: the data of the Mongo installed with "
            f"Workspace stays in the Docker volume of '{WORKSPACE_MONGO_VOLUME}'."
        )
    elif not was_local_mongo and is_local_mongo:
        echo.warning("Workspace now uses the Mongo installed with it. Data in the external MongoDB is not moved.")
    if not existing.get("REDIS_URL") and env.get("REDIS_URL"):
        echo.warning("Workspace now uses the external Redis. Data is not moved.")
    elif existing.get("REDIS_URL") and not env.get("REDIS_URL"):
        echo.warning("Workspace now uses the Redis installed with it. Data in the external Redis is not moved.")


@app.command()
def set(
    directory: Path = directory_option(),
    env_name: str = typer.Argument(..., help="Name of the setting, as in .env.", callback=lambda x: x.upper()),
    env_value: str = typer.Argument(
        "",
        help="Value of the setting. Empty removes an optional setting from .env (the app's default or off); required "
        "settings cannot be removed, an empty PUBLIC_URL or MCP_AUTH_TOKEN gets its default or a new generated one, "
        "and an empty DF_WORKSPACE_BIND_ADDRESS means all interfaces.",
    ),
    no_restart: bool = typer.Option(False, "--no-restart", help="Skip restarting Workspace after the change."),
) -> None:
    """Set one setting in the Workspace .env file and rebuild compose.yaml from it."""
    check_workspace_directory(directory)
    existing = read_installed_env(directory)
    try:
        value = _validated_value(env_name, env_value)
        env = _new_env(existing, env_name, value)
        problems = validate_env(env)
        removed = env_name not in env
        if env_name not in ENV_METADATA and not removed:
            echo.warning(f"{env_name} is not a known DeepFellow Workspace setting; it is written as given.")
        write_stack(directory, env, reset=(env_name,) if removed else (), images=current_service_images(directory))
    except InstallError as exc:
        echo.error(str(exc))
        raise typer.Exit(1) from exc

    if removed:
        echo.success(f"{env_name} removed from {directory / '.env'}.")
    else:
        echo.success(f"{env_name} set in {directory / '.env'}.")
    _warn_about_switches(existing, env)
    if env_name == "MCP_AUTH_TOKEN" and not value:
        echo.info(
            "A new MCP_AUTH_TOKEN was generated, so the /mcp endpoint stays protected; "
            "give it to MCP clients (see 'workspace env info --secret')."
        )
    if problems:
        echo.warning(
            "; ".join(problems) + ". DeepFellow Workspace will not start until they are set, so it is not restarted."
        )
        return
    offer_restart(directory, "change", no_restart)
