# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Config for CLI."""

import json
import re
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import typer

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


_ENV_VALUE_ESCAPES: dict[str, str] = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t"}
_ENV_VALUE_UNESCAPES: dict[str, str] = {"\\": "\\", '"': '"', "n": "\n", "t": "\t"}


def _needs_env_value_quoting(value: str) -> bool:
    """Whether `value` contains a character that requires double-quoting to round-trip."""
    return any(ch in _ENV_VALUE_ESCAPES for ch in value)


def _escape_env_value(value: str) -> str:
    """Escape `value` for storage inside a double-quoted .env entry, one character at a time.

    A single left-to-right pass (as opposed to `str.replace()` chained per escape sequence) is
    required so that a literal backslash already in the value can never combine with an
    adjacent, unrelated character to form a bogus escape sequence on decode.
    """
    return "".join(_ENV_VALUE_ESCAPES.get(char, char) for char in value)


def _unescape_env_value(value: str) -> str:
    """Reverse `_escape_env_value` in a single left-to-right pass (see its docstring for why)."""
    return re.sub(r"\\(.)", lambda m: _ENV_VALUE_UNESCAPES.get(m.group(1), m.group(0)), value)


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
            echo.warning(f"Skipping malformed line in {file_path.as_posix()}: {line!r}")
            continue

        key, value = match.groups()

        # A value only counts as quoted when the quotes actually wrap it, not merely appear in it -
        # otherwise an unquoted value that happens to contain a lone `"` (e.g. embedded JSON) is
        # mistaken for a quoted one and corrupted by the unescape step below.
        is_double_quoted = len(value) >= 2 and value.startswith('"') and value.endswith('"')
        is_single_quoted = len(value) >= 2 and value.startswith("'") and value.endswith("'")

        if is_double_quoted or is_single_quoted:
            value = value[1:-1]

        if is_double_quoted:
            value = _unescape_env_value(value)

        env_vars[key] = value

    return env_vars


def read_env_file_to_dict(env_file: Path) -> EnvDict:
    """Read envs and return as deep dict."""
    if env_file.exists():
        original_env_vars = read_env_file(env_file)
        return env_to_dict(original_env_vars)

    return {}


def read_config_json_settings(config_json_file: Path) -> dict[str, Any]:
    """Best-effort read of a server/infra config.json's "settings" section.

    config.json is written by the running service (not this CLI) as
    ``{"schema_version": ..., "settings": {...}}``. A missing file, unreadable file, invalid JSON, or a
    "settings" value that isn't a dict is treated as "no config.json values available" rather than an
    error, since this is only ever used to avoid overwriting a value that's genuinely there.

    Args:
        config_json_file: Path to the config.json file.

    Returns:
        The "settings" dict, or {} if unavailable for any reason.
    """
    try:
        data = json.loads(config_json_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}

    settings = data.get("settings") if isinstance(data, dict) else None
    return settings if isinstance(settings, dict) else {}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `overlay` over `base`; `overlay`'s leaf values win on conflicts.

    The standard library has no recursive dict-merge helper (`dict.update()`/`{**a, **b}`/
    `ChainMap` are all shallow). Third-party packages exist (`deepmerge`, `mergedeep`), but aren't
    worth adding as a dependency for this one call site.
    """
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        elif isinstance(value, dict) and isinstance(merged.get(key), str):
            merged[key] = json.dumps(value)  # NOTE: needed to properly parse DF_PLUGINS_SETUP
        else:
            merged[key] = value
    return merged


def merge_config_json_into_env(env_content: EnvDict, config_json_settings: dict[str, Any]) -> EnvDict:
    """Overlay a config.json "settings" dict onto a .env-derived EnvDict, config.json winning.

    config.json's settings keys aren't "df_"-prefixed (unlike .env's, once read through
    read_env_file_to_dict()/env_to_dict()), so its top-level keys are prefixed with "df_" first -
    the same convention env_to_dict() already uses - before deep-merging it over `env_content`. The
    merge is recursive so a nested field only `.env` has (e.g. a sibling key under the same
    "df_vector_database" tree that config.json doesn't carry) survives instead of being dropped by a
    shallow top-level overwrite.

    Args:
        env_content: The prior install's .env content, as read by read_env_file_to_dict().
        config_json_settings: The prior install's config.json "settings" content, as read by
            read_config_json_settings() (empty if config.json doesn't exist or has no "settings").

    Returns:
        A new EnvDict with config_json_settings's values merged in, taking precedence over
        env_content's for any field present in both.
    """
    prefixed = {f"df_{key}": value for key, value in config_json_settings.items()}
    return cast("EnvDict", _deep_merge(env_content, prefixed))


def save_env_file(
    env_file: Path,
    values: Mapping[str, str | int],
    docker_note: bool = True,
    quiet: bool = False,
    remove: Iterable[str] = (),
) -> None:
    """Creates or updates .env file with provided values.

    Args:
        env_file: Path to the .env file.
        values: Values to add or overwrite.
        docker_note: Whether to prepend the Docker Compose header comment.
        quiet: Whether to log the write via echo.debug instead of echo.info.
        remove: Keys to drop from the file. Applied after merging `values`, so omitting a key
            from `values` alone does not delete it — the file is re-read and merged with the
            existing content, which would otherwise restore any key not explicitly removed.
    """
    # Load existing values if file exists
    existing_vars = {}
    file_existed = env_file.exists()
    if file_existed:
        existing_vars = read_env_file(env_file)

    env_file.parent.mkdir(exist_ok=True)

    # Merge existing with new values (new values take precedence)
    final_vars = {**existing_vars, **values}
    for key in remove:
        final_vars.pop(key, None)

    content = "# Docker Compose Environment Variables\n# Edit these values as needed\n\n" if docker_note else ""
    for key, value in final_vars.items():
        str_value = str(value)
        if _needs_env_value_quoting(str_value):
            content += f'{key}="{_escape_env_value(str_value)}"\n'
        else:
            content += f"{key}={str_value}\n"

    env_file.write_text(content)

    action = "Updated" if file_existed else "Generated"
    msg = echo.debug if quiet else echo.info
    msg(f"{action} {env_file.as_posix()}.")


def parse_key_value_updates(pairs: list[str]) -> dict[str, Any]:
    """Parse ``key=value`` CLI arguments into a typed dict, JSON-decoding each value where possible.

    Args:
        pairs: List of ``key=value`` strings, e.g. ``["otel_tracing_enabled=true", "name=foo"]``.

    Returns:
        Dict mapping each key to its JSON-decoded value, or the raw string if it isn't valid JSON.

    Raises:
        typer.Exit: If any pair is missing the ``=`` separator.
    """
    updates: dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            echo.error(f"Invalid key=value pair: {pair}")
            raise typer.Exit(1)
        key, raw_value = pair.split("=", 1)
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            value = raw_value
        updates[key] = value
    return updates


def reveal_secret_entries(config: dict[str, Any], reveal: Callable[[str], str]) -> None:
    """Replace masked values of secret entries in an Infra-style /admin/config response.

    Args:
        config: A response shaped like ``{"entries": [{"key": ..., "is_secret": ..., "value": ...}, ...]}``,
            mutated in place.
        reveal: Called with an entry's ``key`` for each entry where ``is_secret`` is true; must return
            the revealed value.
    """
    for entry in config.get("entries", []):
        if entry.get("is_secret"):
            entry["value"] = reveal(entry["key"])


SECRET_MASK = "••••••••"


def reveal_masked_paths(config: dict[str, Any], reveal: Callable[[str], str], mask: str = SECRET_MASK) -> None:
    """Replace masked leaf values in a Server-style /admin/config response with their revealed values.

    Unlike Infra's response (an ``entries`` list with per-field ``is_secret`` metadata), Server's
    /admin/config masks a fixed set of dotted-path fields in place within an otherwise plain nested
    dict (e.g. ``{"smtp": {"password": "••••••••"}}``). A masked leaf is detected by value equality
    with `mask` and revealed by calling `reveal` with its dotted path (e.g. ``"smtp.password"``).

    Args:
        config: A nested dict response, mutated in place.
        reveal: Called with a masked leaf's dotted path; must return the revealed value.
        mask: The sentinel value a masked secret is set to.
    """

    def _walk(node: dict[str, Any], prefix: tuple[str, ...]) -> None:
        for key, value in node.items():
            path = (*prefix, key)
            if isinstance(value, dict):
                _walk(value, path)
            elif value == mask:
                node[key] = reveal(".".join(path))

    _walk(config, ())


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
