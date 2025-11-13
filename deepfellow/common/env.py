"""Helper do komend env."""

from pathlib import Path
from typing import Any

import typer

from deepfellow.common.config import read_env_file, save_env_file
from deepfellow.common.echo import echo


def env_set(
    env_file: Path,
    env_name: str,
    env_value: str,
    df_prefix: bool = True,
    should_raise: bool = True,
    quiet: bool = False,
    **kwargs: Any,
) -> None:
    """Set env value in the directpry/.env file."""
    if not env_file.is_file() and should_raise:
        echo.error(f"Environment file not found: {env_file}")
        raise typer.Exit(1)

    envs: dict[str, str] = {}

    if env_file.is_file():
        envs = read_env_file(env_file)

    env_name = env_name.upper()
    if df_prefix and not env_name.startswith("DF_"):
        echo.debug("Added the DF_ prefix to the variable name")
        env_name = f"DF_{env_name}"

    envs[env_name] = env_value
    save_env_file(env_file, envs, quiet=quiet, **kwargs)


def env_get(env_file: Path, env_name: str, df_prefix: bool = True, should_raise: bool = True) -> str | None:
    """Set env value in the directpry/.env file."""
    if not env_file.is_file() and should_raise:
        echo.error(f"Environment file not found: {env_file}")
        raise typer.Exit(1)

    envs: dict[str, str] = {}

    if env_file.is_file():
        envs = read_env_file(env_file)

    env_name = env_name.upper()
    if df_prefix and not env_name.startswith("DF_"):
        echo.debug("Added the DF_ prefix to the variable name")
        env_name = f"DF_{env_name}"

    return envs.get(env_name)


def get_envs_list(env_file: Path) -> list[str]:
    """Return a list of strings representing the envs."""
    if not env_file.is_file():
        echo.error(f"Environment file not found: {env_file}")
        raise typer.Exit(1)

    envs = read_env_file(env_file)
    return [f"{env}={value}" for env, value in envs.items()]
