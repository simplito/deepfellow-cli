# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Install model core logic."""

from dataclasses import dataclass
from typing import Any

import typer

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import InfraInstallSkippedError
from deepfellow.infra.utils.connection import (
    call_infra,
    cancel_model_install,
    cancel_on_interrupt,
    resolve_infra_connection,
)
from deepfellow.infra.utils.fields import parse_spec_json
from deepfellow.infra.utils.progress import install_with_progress


@dataclass
class ModelInstallConnection:
    """Result of `resolve_connection`: everything `apply_install` needs to install the model."""

    server: str
    api_key: str


def resolve_connection(server: str | None = None) -> ModelInstallConnection:
    """Resolve the infra connection to use for a model install, performing no install API call.

    Args:
        server: Infra server URL. Resolved from config/prompt if not given.

    Returns:
        The resolved connection, ready to pass to `apply_install`.
    """
    server, api_key = resolve_infra_connection(server)
    return ModelInstallConnection(server=server, api_key=api_key)


def apply_install(
    service_name: str,
    model_name: str,
    connection: ModelInstallConnection,
    spec: dict[str, Any] | None = None,
    quiet: bool = False,
) -> None:
    """Install a model by calling the install API with an already-resolved connection. Prompts nothing.

    Args:
        service_name: Name of the service the model belongs to (e.g. "ollama").
        model_name: Name of the model to install.
        connection: The connection built by `resolve_connection`.
        spec: Model install spec sent as-is. Fields left out fall back to infra's own defaults.
        quiet: Suppress the "Updated ..." confirmation when the resolved server/API key are
            re-persisted - e.g. suite install --resume calls this repeatedly (once per model) with
            the exact same, already-confirmed connection, so re-announcing it every time is noise.
    """
    server, api_key = connection.server, connection.api_key
    url = f"{server}/admin/services/{service_name}/models/_?model_id={model_name}"

    try:
        data = cancel_on_interrupt(
            lambda: call_infra(
                lambda: install_with_progress(
                    url, api_key, data={"spec": spec or {}}, message=f"Installing model {model_name}..."
                ),
                "Unable to install model.",
                server=server,
                api_key=api_key,
                quiet=quiet,
                skip_if_message_contains="already installed",
                retry_if_message_contains="already installing",
            ),
            lambda: cancel_model_install(server, api_key, service_name, model_name),
            f"model '{model_name}'",
        )
    except InfraInstallSkippedError:
        echo.info(f"Model '{model_name}' is already installed; skipping.")
        return

    if data.get("status", "").lower() != "ok":
        message = data.get("details")
        echo.error(f"Unable to install model.{f' {message}' if message else ''}")
        if not message:
            echo.error("Check `docker compose logs infra` for details.")
        raise typer.Exit(1)

    echo.success(f"Model {model_name} installed.")


def install(
    service_name: str,
    model_name: str,
    server: str | None = None,
    spec: str | None = None,
    quiet: bool = False,
) -> None:
    """Install model.

    Args:
        service_name: Name of the service the model belongs to (e.g. "ollama").
        model_name: Name of the model to install.
        server: Infra server URL. Resolved from config/prompt if not given.
        spec: Model install spec as a JSON object. Fields left out fall back to infra's own defaults.
        quiet: Suppress the "Updated ..." confirmation when the resolved server/API key are
            re-persisted - e.g. suite install --resume calls this repeatedly (once per model) with
            the exact same, already-confirmed connection, so re-announcing it every time is noise.
    """
    parsed_spec = parse_spec_json(spec)
    connection = resolve_connection(server)
    apply_install(service_name, model_name, connection, spec=parsed_spec, quiet=quiet)
