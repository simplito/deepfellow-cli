# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Config for CLI."""

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from deepfellow.common.echo import echo


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
    result: EnvDict = {}

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
        # moving pointer
        current: dict[str, Any] = result

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


def read_env_file_to_dict(env_file: Path) -> EnvDict:
    """Read envs and return as deep dict."""
    if env_file.exists():
        original_env_vars = read_env_file(env_file)
        return env_to_dict(original_env_vars)

    return {}


def save_env_file(
    env_file: Path, values: Mapping[str, str | int], docker_note: bool = True, quiet: bool = False
) -> None:
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
    msg = echo.debug if quiet else echo.info
    msg(f"{action} {env_file.as_posix()}.")


def configure_uuid_key(name: str, existing: Any) -> str:
    """Generate a new UUID key if required.

    Args:
        name (str): The name of the key.
        existing (Any): The existing value of the key.

    Returns:
        str: The new or existing UUID key.
    """
    if existing is not None and echo.confirm(
        f"There is an existing {name} in the env file. Do you want to keep it?", default=True
    ):
        return existing

    return str(uuid4())
