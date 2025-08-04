"""Config for CLI."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import click
import typer

from deepfellow.common.echo import echo


def get_config_path() -> Path:
    """Get config path from context.

    Args:
        ctx (typer.Context): CLI context object.

    Returns:
       Path: Config file path.

    Raises:
       typer.BadParameter: If no config provided.
    """
    ctx = click.get_current_context()
    if ctx.obj and ctx.obj.get("config-path"):
        config_path = ctx.obj["config-path"]
        # Ensure we return a Path object
        if isinstance(config_path, Path):
            return config_path

        return Path(config_path)

    raise typer.BadParameter("No config provided.")


def load_config(raise_on_error: bool = False) -> dict[str, Any]:
    """Load and parse config file.

    Args:
        raise_on_error (bool, optional): Whether to raise on error loading config. Defaults to False.

    Returns:
        dict[str, Any]: Config object

    Raises:
        FileNotFoundError: If no config file found
        Exit: If error loading config
    """
    config_path = get_config_path()

    try:
        content = config_path.read_text(encoding="utf-8")
        return json.loads(content)
    except FileNotFoundError:
        msg = f"Config file not found: {config_path}"
        echo.debug(msg)
        if raise_on_error:
            echo.error(msg)
            raise
    except PermissionError as exc:
        echo.error(f"Permission denied reading config file: {config_path}")
        if raise_on_error:
            raise typer.Exit(1) from exc
    except json.JSONDecodeError as exc:
        echo.error(f"Error parsing config file: {exc}")
        if raise_on_error:
            raise typer.Exit(1) from exc
    except UnicodeDecodeError as exc:
        echo.error(f"Error reading config file (encoding issue): {exc}")
        if raise_on_error:
            raise typer.Exit(1) from exc

    return {}


def store_config(config_data_source: dict[str, Any], update: bool = True) -> None:
    """Store/save config data to file.

    Args:
        config_data_source (dict[str, Any]): Config data to store
        update (bool): If True, load and update existing config

    Raises:
       Exit: If the config file cannot be written to disk and any OS error
    """
    config_path = get_config_path()
    config_data = deepcopy(config_data_source)

    if update:
        try:
            current_config = json.loads(config_path.read_text(encoding="utf-8"))
            config_data = {**current_config, **config_data}
        except FileNotFoundError:
            # No previous config, just write the new one
            pass

    try:
        # Create parent directories if they don't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write JSON with pretty formatting
        content = json.dumps(config_data, indent=2, ensure_ascii=False)
        config_path.write_text(content, encoding="utf-8")
    except PermissionError as exc:
        echo.error(f"Permission denied writing config file: {config_path}")
        raise typer.Exit(1) from exc
    except OSError as exc:
        echo.error(f"Error writing config file: {exc}")
        raise typer.Exit(1) from exc

    typer.echo(f"Config saved to: {config_path}")
