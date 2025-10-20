"""Helper do komend env."""

from pathlib import Path

import typer

from deepfellow.common.config import read_env_file, save_env_file
from deepfellow.common.echo import echo


def env_set(directory: Path, env_name: str, env_value: str, df_prefix: bool) -> None:
    """Set env value in the directpry/.env file."""
    env_file = directory / ".env"
    if not env_file.is_file():
        echo.error(f"Environment file not found: {env_file}")
        raise typer.Exit(1)

    envs = read_env_file(env_file)

    if df_prefix and not env_name.startswith("DF_"):
        echo.info("Added the DF_ prefix to the variable name")
        env_name = f"DF_{env_name}"

    envs[env_name] = env_value
    save_env_file(env_file, envs)


def get_envs_list(env_file: Path) -> list[str]:
    """Return a list of strings representing the envs."""
    if not env_file.is_file():
        echo.error(f"Environment file not found: {env_file}")
        raise typer.Exit(1)

    envs = read_env_file(env_file)
    return [f"{env}={value}" for env, value in envs.items()]
