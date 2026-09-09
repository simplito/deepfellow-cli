# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared helpers for building an install spec from an Infra field schema.

Both `infra service install` and `infra mcp install` install something described by the same
`{"fields": [...]}` schema shape (name/type/required/default/values per field) and need to
resolve it into a concrete spec dict from the same sources, in the same order: `--set` flags,
then `--api-key` (for an `api_key` field), then an interactive prompt, then the field's default.
"""

import json
from typing import Any, cast

import typer

from deepfellow.common.echo import echo, is_interactive
from deepfellow.common.registry import list_image_tags


def parse_spec_json(spec: str | None) -> dict[str, Any]:
    """Parse a `--spec` JSON object option into a dict."""
    if spec is None:
        return {}
    try:
        parsed = json.loads(spec)
    except json.JSONDecodeError as exc:
        echo.error(f"Invalid JSON in --spec: {exc}")
        raise typer.Exit(1) from exc
    if not isinstance(parsed, dict):
        echo.error("--spec must be a JSON object, not an array or scalar.")
        raise typer.Exit(1)
    return parsed


def parse_set_args(set_args: list[str]) -> dict[str, str]:
    """Parse `--set key=value` arguments into a dict."""
    result: dict[str, str] = {}
    for item in set_args:
        if "=" not in item:
            echo.error(f"Invalid --set value '{item}'. Expected format: key=value")
            raise typer.Exit(1)
        key, _, value = item.partition("=")
        result[key.strip()] = value
    return result


def normalize_field_description(description: Any) -> str:
    """Collapse a field description's whitespace (including embedded newlines) onto one line.

    Infra's field descriptions routinely embed a literal newline (e.g. `"Custom environmental
    variables.\\nRequired variables: BRAVE_API_KEY"`), which breaks a one-line ``- name:
    description (default: ...)`` rendering into a stray unindented continuation line instead.
    """
    return " ".join(str(description).split())


def format_field_options(field: dict[str, Any]) -> str:
    """Format the available options of a ``oneof`` field, e.g. ``available: GPU, CPU``.

    Returns an empty string if the field carries no ``values`` list.
    """
    values = field.get("values") or []
    if not values:
        return ""

    options = [value.get("value", str(value)) if isinstance(value, dict) else str(value) for value in values]
    return f"available: {', '.join(options)}"


def format_field(field: dict[str, Any]) -> str:
    """Format a single spec field as ``- {name}: {description} (default: {default})``.

    For ``oneof`` fields (those carrying a ``values`` list), the available options are
    appended so the user knows what values may be passed, e.g.
    ``- hardware: Choose hardware: (default: GPU, available: GPU, CPU)``.
    """
    name = field.get("name")
    description = normalize_field_description(field.get("description"))
    default = field.get("default")
    detail = f"default: {default}"

    options = format_field_options(field)
    if options:
        detail += f", {options}"

    return f"- {name}: {description} ({detail})"


def resolve_oneof_choices(values: list[Any]) -> list[str]:
    """Normalize oneof values to a flat list of string choices."""
    choices = []
    for v in values:
        if isinstance(v, dict):
            choices.append(v.get("value", str(v)))
        else:
            choices.append(str(v))
    return choices


def build_spec_from_fields(  # noqa: C901
    fields: list[dict[str, Any]],
    set_values: dict[str, str],
    api_key: str | None,
    prompt_all: bool,
) -> dict[str, Any]:
    """Build a spec dict from a `{"fields": [...]}` schema.

    Resolves each field's value in this order: --set flag > --api-key (for an api_key field) >
    interactive prompt > default. In non-interactive mode, required fields without a value cause
    an error.

    Args:
        fields: List of field definitions from the spec schema.
        set_values: Values provided via --set key=value flags, keyed by field name.
        api_key: Value provided via --api-key, applied to the api_key field if present.
        prompt_all: If True, prompt for optional fields too, not only required ones.

    Returns:
        Dict mapping field names to resolved values, ready to send as the install spec.
    """
    spec: dict[str, Any] = {}
    for field in fields:
        field_name: str | None = field.get("name")
        if not field_name:
            echo.error("Malformed spec: field missing 'name'. Please report this as a server bug.")
            raise typer.Exit(1)
        field_name = cast("str", field_name)
        field_type = field.get("type")
        if not field_type:
            echo.error(f"Malformed spec: field '{field_name}' missing 'type'. Please report as a server bug.")
            raise typer.Exit(1)
        field_type = cast("str", field_type)
        required: bool = field.get("required", False)
        default: Any = field.get("default")
        description: str = normalize_field_description(field.get("description", field_name))
        values: list[Any] = field.get("values") or []

        if field_name in set_values:
            spec[field_name] = set_values[field_name]
            continue

        if field_name == "api_key" and api_key is not None:
            spec[field_name] = api_key
            continue

        if not is_interactive():
            if required and default is None:
                echo.error(f"Field '{field_name}' is required. Use --set {field_name}=<value>")
                raise typer.Exit(1)
            if required and default is not None:
                spec[field_name] = default
            continue

        should_prompt = required or prompt_all

        docker_tags: list[str] = []
        if field_type == "docker-tags" and should_prompt and field.get("docker_image"):
            docker_tags = list_image_tags(cast("str", field["docker_image"]))

        if field_type == "oneof" and values and should_prompt:
            choices = resolve_oneof_choices(values)
            current_default = default if default in choices else choices[0]
            value = echo.choice(description, choices=choices, default=current_default)
            spec[field_name] = value
        elif field_type == "docker-tags" and docker_tags:
            # Offer the actual tags available on the registry instead of asking the user to type
            # a version blind; falls through to a free-text prompt below when the registry can't
            # be reached or reports none.
            current_default = default if default in docker_tags else docker_tags[0]
            value = echo.choice(description, choices=docker_tags, default=current_default)
            spec[field_name] = value
        elif (field_type == "password" or field_name == "api_key") and should_prompt:
            if required:
                value = echo.prompt_until_valid(
                    description,
                    lambda v: v if v else None,
                    error_message=(
                        f"'{field_name}' is required and cannot be empty. You can use --set {field_name}=value instead."
                    ),
                    password=True,
                )
                spec[field_name] = value
            else:
                value = echo.prompt(description, password=True, default=default or "")
                if value == "":
                    confirmed = echo.confirm(f"'{field_name}' is empty. Do you want to continue?")
                    if not confirmed:
                        raise typer.Exit(1)

                if value != "":
                    spec[field_name] = value
        elif should_prompt and default is None:
            value = echo.prompt(description)
            if required or (value is not None and value != ""):
                spec[field_name] = value
        elif should_prompt:
            value = echo.prompt(description, default=default)
            if value is not None and value != "":
                spec[field_name] = value

    return spec
