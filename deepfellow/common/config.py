"""Config for CLI."""

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

import click
import typer

from deepfellow.common.echo import echo


def get_config_path() -> Path:
    """Get config path from context.

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
        if raise_on_error:
            echo.error(msg)
            raise

        echo.debug(msg)
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
        config_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(config_data, indent=2, ensure_ascii=False)
        config_path.write_text(content, encoding="utf-8")
    except PermissionError as exc:
        echo.error(f"Permission denied writing config file: {config_path}")
        raise typer.Exit(1) from exc
    except OSError as exc:
        echo.error(f"Error writing config file: {exc}")
        raise typer.Exit(1) from exc

    echo.info(f"Config saved to: {config_path}")


def dict_to_env(data: dict[str, Any], prefix: str = "DF_", parent_key: str = "") -> dict[str, str]:
    """Convert a nested dictionary to environment variable format.

    Args:
        data: Dictionary to convert (values can be string, int, or nested dict)
        prefix: Optional prefix for environment variables (default "DF_")
        parent_key: Used internally for recursion

    Returns:
        Dictionary of environment variables (all values as strings)
    """
    env_vars = {}

    for key, value in data.items():
        full_key = f"{parent_key}__{key.upper()}" if parent_key else f"{prefix}{key.upper()}" if prefix else key.upper()

        if isinstance(value, dict):
            # Recursively handle nested dictionaries
            env_vars.update(dict_to_env(value, prefix="", parent_key=full_key))
        else:
            env_vars[full_key] = str(value)

    return env_vars


EnvDict = dict[str, str | int | dict[str, Any]]


def env_to_dict(env_vars: dict[str, str], prefix: str = "") -> EnvDict:
    """Convert environment variables back to nested dictionary format.

    Args:
        env_vars: Dictionary of environment variables (all values as strings)
        prefix: Optional prefix to filter by (e.g., "DF_")

    Returns:
        Nested dictionary with appropriate types (string, int, or nested dict)
    """
    result = {}

    # Filter environment variables by prefix if provided
    filtered_vars = {}
    for key, value in env_vars.items():
        if prefix and key.startswith(prefix):
            # Remove prefix from key
            clean_key = key[len(prefix) :]
            filtered_vars[clean_key] = value
        elif not prefix:
            filtered_vars[key] = value

    # Build nested dictionary
    for key, value in filtered_vars.items():
        keys = key.split("__")
        current = result

        # Navigate through the nested structure
        for i, k in enumerate(keys):
            k = k.lower()  # Convert to lowercase for dict keys
            if i == len(keys) - 1:
                # Last key, set the value
                # Try to convert to appropriate type
                if value.isdigit():
                    current[k] = int(value)
                elif value.lower() in ("true", "false"):
                    current[k] = value.lower() == "true"
                else:
                    current[k] = value
            else:
                # Intermediate key, create nested dict if doesn't exist
                if k not in current:
                    current[k] = {}

                current = current[k]

    return result


def read_env_file(file_path: str | Path) -> dict[str, str]:
    """Read environment variables from a .env file.

    Args:
        file_path: Path to the .env file

    Returns:
        Dictionary of environment variables {env_name: env_value}
    """
    env_vars = {}
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Environment file not found: {file_path}")

    lines = file_path.read_text(encoding="utf-8").splitlines()

    for line in lines:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        # Match KEY=VALUE pattern (with optional quotes)
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
        if not match:
            continue  # Skip malformed lines

        key, value = match.groups()

        # Remove surrounding quotes if present
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        # Handle escape sequences in double quotes
        if '"' in line and not value.startswith("'"):
            value = value.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').replace("\\\\", "\\")

        env_vars[key] = value

    return env_vars


def save_env_file(env_file: Path, values: Mapping[str, str | int], docker_note: bool = True) -> None:
    """Creates or updates .env file with provided values."""
    # Load existing values if file exists
    existing_vars = {}
    file_existed = env_file.exists()
    if file_existed:
        existing_vars = read_env_file(env_file)

    env_file.parent.mkdir(exist_ok=True)

    # Merge existing with new values (new values take precedence)
    final_vars = {**existing_vars, **values}

    content = "# Docker Compose Environment Variables\n# Edit these values as needed\n\n" if docker_note else ""
    for key, value in final_vars.items():
        content += f"{key}={value}\n"

    env_file.write_text(content)

    action = "Updated" if file_existed else "Generated"
    echo.info(f"{action} {env_file.as_posix()}.")


def configure_uuid_key(name: str, existing: str | None) -> str:
    """Generate a new UUID key if required.

    Args:
        name (str): The name of the key.
        existing (str | None): The existing value of the key.

    Returns:
        str: The new or existing UUID key.
    """
    if existing is not None and echo.confirm(
        f"There is an existing {name} in the env file. Do you want to keep it?", default=True
    ):
        return existing

    new_value = str(uuid4())
    if echo.confirm(f"{name} created. Is it safe to print it here?"):
        echo.info(f"{name}: {new_value}")

    return new_value
