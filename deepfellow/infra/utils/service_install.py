# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install service core logic."""

from dataclasses import dataclass
from typing import Any

import typer

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import InfraInstallSkippedError
from deepfellow.common.rest import get
from deepfellow.infra.utils.connection import call_infra, resolve_infra_connection
from deepfellow.infra.utils.fields import build_spec_from_fields, parse_set_args, parse_spec_json
from deepfellow.infra.utils.progress import install_with_progress


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
    return build_spec_from_fields(api_fields, set_values, service_api_key, prompt_all=prompt_all)


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
    parsed_spec: dict[str, Any] | None = parse_spec_json(spec) if spec else None
    set_values = parse_set_args(set_args or [])

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
