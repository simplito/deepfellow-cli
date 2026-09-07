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
from dataclasses import dataclass
from typing import Any, cast

import typer

from deepfellow.common.echo import echo, is_interactive
from deepfellow.common.exceptions import InfraInstallSkippedError
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


@dataclass
class ServiceInstallSpec:
    """Result of `build_spec`: everything `apply_spec` needs to install the service."""

    server: str
    api_key: str
    spec: dict[str, Any]
    explicit_spec: bool
    """Whether `spec` came from an explicit `--spec`, skipping field resolution/prompting."""


def build_spec(
    name: str,
    server: str | None = None,
    service_api_key: str | None = None,
    spec: str | None = None,
    set_args: list[str] | None = None,
    prompt_all: bool = True,
) -> ServiceInstallSpec:
    """Resolve connection info and build a service's install spec, performing no install API call.

    Args:
        name: Service name to install (e.g. "ollama").
        server: Infra server URL. Resolved from config/prompt if not given.
        service_api_key: Value for the service's "api_key" spec field, if it has one.
        spec: JSON spec to send as-is, skipping the interactive/`--set` field resolution.
        set_args: `key=value` overrides for individual spec fields.
        prompt_all: Prompt for optional fields too, not only required ones.

    Returns:
        The resolved connection info and install spec, ready to pass to `apply_spec`.
    """
    if spec is not None and not spec.strip():
        echo.error("--spec cannot be empty.")
        raise typer.Exit(1)

    if spec is not None and set_args:
        echo.error("--spec and --set cannot be used together. Use one or the other.")
        raise typer.Exit(1)
    parsed_spec: dict[str, Any] | None = _parse_spec(spec) if spec else None
    set_values = _parse_set_args(set_args or [])

    server, api_key = resolve_infra_connection(server)

    spec_res = _resolve_spec(parsed_spec, server, api_key, name, set_values, service_api_key, prompt_all=prompt_all)

    return ServiceInstallSpec(server=server, api_key=api_key, spec=spec_res, explicit_spec=parsed_spec is not None)


def apply_spec(name: str, install_spec: ServiceInstallSpec, quiet: bool = False) -> None:
    """Install a service by calling the install API with an already-built spec. Prompts nothing.

    Args:
        name: Service name to install (e.g. "ollama").
        install_spec: The connection info and spec built by `build_spec`.
        quiet: Suppress the "Updated ..." confirmation when the resolved server/API key are
            re-persisted - e.g. suite install --resume calls this repeatedly against a connection
            already confirmed by an earlier step in the same run, so re-announcing it is noise.
    """
    server, api_key = install_spec.server, install_spec.api_key
    url = f"{server}/admin/services/{name}"

    try:
        data = call_infra(
            lambda: install_with_progress(url, api_key, data={"spec": install_spec.spec}),
            "Unable to install service",
            server=server,
            api_key=api_key,
            quiet=quiet,
            skip_if_message_contains="already installed",
            retry_if_message_contains="already installing",
        )
    except InfraInstallSkippedError:
        echo.info(f"Service '{name}' is already installed; skipping.")
        return

    if data.get("status", "").lower() != "ok":
        message = data.get("details")
        echo.error(f"Unable to install service.{f' {message}' if message else ''}")
        if not message:
            echo.error("Check `docker compose logs infra` for details.")
        raise typer.Exit(1)

    echo.success(f"Service {name} installed.")


def install(
    name: str,
    server: str | None = None,
    service_api_key: str | None = None,
    spec: str | None = None,
    set_args: list[str] | None = None,
    prompt_all: bool = True,
    quiet: bool = False,
) -> None:
    """Install service.

    Args:
        name: Service name to install (e.g. "ollama").
        server: Infra server URL. Resolved from config/prompt if not given.
        service_api_key: Value for the service's "api_key" spec field, if it has one.
        spec: JSON spec to send as-is, skipping the interactive/`--set` field resolution.
        set_args: `key=value` overrides for individual spec fields.
        prompt_all: Prompt for optional fields too, not only required ones.
        quiet: Suppress the "Updated ..." confirmation when the resolved server/API key are
            re-persisted - e.g. suite install --resume calls this with an explicit spec (so it
            wouldn't otherwise go quiet), but the connection was already confirmed by an earlier
            step in the same run, so re-announcing it is noise.
    """
    install_spec = build_spec(
        name, server=server, service_api_key=service_api_key, spec=spec, set_args=set_args, prompt_all=prompt_all
    )
    apply_spec(name, install_spec, quiet=quiet or not install_spec.explicit_spec)
