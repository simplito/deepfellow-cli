# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install service core logic."""

import json
from typing import Any, cast

import typer

from deepfellow.common.echo import echo, is_interactive
from deepfellow.common.rest import get
from deepfellow.infra.utils.connection import call_infra, resolve_infra_connection
from deepfellow.infra.utils.progress import install_with_progress


def _parse_spec(spec: str | None) -> dict[str, Any]:
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


def _parse_set_args(set_args: list[str]) -> dict[str, str]:
    """Parse --set key=value arguments into a dict."""
    result: dict[str, str] = {}
    for item in set_args:
        if "=" not in item:
            echo.error(f"Invalid --set value '{item}'. Expected format: key=value")
            raise typer.Exit(1)
        key, _, value = item.partition("=")
        result[key.strip()] = value
    return result


def _fetch_service_spec(server: str, api_key: str, name: str) -> list[dict[str, Any]]:
    """Fetch service spec fields from the API."""
    url = f"{server}/admin/services/{name}"
    data = call_infra(
        lambda: get(url, api_key, item_name="Service spec", reraise=True),
        "Unable to fetch service spec",
        server=server,
        api_key=api_key,
    )
    return data.get("spec", {}).get("fields", [])


def _resolve_oneof_choices(values: list[Any]) -> list[str]:
    """Normalize oneof values to a flat list of string choices."""
    choices = []
    for v in values:
        if isinstance(v, dict):
            choices.append(v.get("value", str(v)))
        else:
            choices.append(str(v))
    return choices


def _build_spec_from_api(  # noqa: C901
    fields: list[dict[str, Any]],
    set_values: dict[str, str],
    service_api_key: str | None,
    prompt_all: bool,
) -> dict[str, Any]:
    """Build spec dict from API-provided field definitions.

    Resolves values in this order: --set flag > --api-key (for api_key field) > interactive prompt > default.
    In non-interactive mode, required fields without a value cause an error.
    With prompt_all=True, optional fields are also prompted interactively.

    Args:
        fields: List of field definitions from the service spec API response.
        set_values: Values provided via --set key=value flags, keyed by field name.
        service_api_key: Value provided via --api-key, applied to the api_key field if present.
        prompt_all: If True, prompt for optional fields too, not only required ones.

    Returns:
        Dict mapping field names to resolved values, ready to send as the install spec.
    """
    spec: dict[str, Any] = {}
    for field in fields:
        field_name: str | None = field.get("name")
        if not field_name:
            echo.error("Malformed service spec: field missing 'name'. Please report this as a server bug.")
            raise typer.Exit(1)
        field_name = cast("str", field_name)
        field_type = field.get("type")
        if not field_type:
            echo.error(f"Malformed service spec: field '{field_name}' missing 'type'. Please report as a server bug.")
            raise typer.Exit(1)
        field_type = cast("str", field_type)
        required: bool = field.get("required", False)
        default: Any = field.get("default")
        description: str = field.get("description", field_name)
        values: list[Any] = field.get("values") or []

        if field_name in set_values:
            spec[field_name] = set_values[field_name]
            continue

        if field_name == "api_key" and service_api_key is not None:
            spec[field_name] = service_api_key
            continue

        if not is_interactive():
            if required and default is None:
                echo.error(f"Field '{field_name}' is required. Use --set {field_name}=<value>")
                raise typer.Exit(1)
            if required and default is not None:
                spec[field_name] = default
            continue

        should_prompt = required or prompt_all

        if field_type == "oneof" and values and should_prompt:
            choices = _resolve_oneof_choices(values)
            current_default = default if default in choices else choices[0]
            value = echo.choice(description, choices=choices, default=current_default)
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


def _resolve_spec(
    parsed_spec: dict[str, Any] | None,
    server: str,
    api_key: str,
    name: str,
    set_values: dict[str, str],
    service_api_key: str | None,
    prompt_all: bool,
) -> dict[str, Any]:
    """Determine the final spec dict to send to the API."""
    if parsed_spec is not None:
        return parsed_spec
    api_fields = _fetch_service_spec(server, api_key, name)
    return _build_spec_from_api(api_fields, set_values, service_api_key, prompt_all=prompt_all)


def install(
    name: str,
    server: str | None = None,
    service_api_key: str | None = None,
    spec: str | None = None,
    set_args: list[str] | None = None,
    prompt_all: bool = True,
) -> None:
    """Install service."""
    if spec is not None and not spec.strip():
        echo.error("--spec cannot be empty.")
        raise typer.Exit(1)

    if spec is not None and set_args:
        echo.error("--spec and --set cannot be used together. Use one or the other.")
        raise typer.Exit(1)
    parsed_spec: dict[str, Any] | None = _parse_spec(spec) if spec else None
    set_values = _parse_set_args(set_args or [])

    server, api_key = resolve_infra_connection(server)

    url = f"{server}/admin/services/{name}"

    spec_res = _resolve_spec(parsed_spec, server, api_key, name, set_values, service_api_key, prompt_all=prompt_all)

    data = call_infra(
        lambda: install_with_progress(url, api_key, data={"spec": spec_res}),
        "Unable to install service",
        server=server,
        api_key=api_key,
        quiet=parsed_spec is None,
    )

    if data.get("status", "").lower() != "ok":
        message = data.get("detail") or data.get("error")
        echo.error(f"Unable to install service.{f' {message}' if message else ''}")
        raise typer.Exit(1)

    echo.success(f"Service {name} installed.")
