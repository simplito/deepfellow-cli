# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Update model core logic."""

from typing import Any

import typer

from deepfellow.common.echo import echo
from deepfellow.infra.utils.connection import (
    call_infra,
    cancel_model_install,
    cancel_on_interrupt,
    quote_id,
    resolve_infra_connection,
)
from deepfellow.infra.utils.models import get_service_models
from deepfellow.infra.utils.progress import install_with_progress
from deepfellow.infra.utils.update_spec import (
    build_updated_spec,
    confirm_version_change,
    installed_spec,
    resolve_image_version,
)


def update(
    service_name: str,
    model_name: str,
    server: str | None = None,
    spec: str | None = None,
    set_args: list[str] | None = None,
    image_version: str | None = None,
) -> None:
    """Change the settings of an installed model, for example its Docker image tag.

    Infra uninstalls the model, installs it again with the new settings, and restores the old ones if
    that fails.

    Args:
        service_name: Name of the service the model belongs to (e.g. "custom").
        model_name: Name of the model to update (e.g. "doc_chunker").
        server: Infra server URL. Resolved from config/prompt if not given.
        spec: JSON object with the changed settings.
        set_args: `key=value` overrides of individual settings.
        image_version: Docker image tag to move the model to. The newest release when neither this nor
            other changes are given.
    """
    server, api_key = resolve_infra_connection(server)

    models = get_service_models(server, api_key, service_name, quiet=True)
    model = next((item for item in models if item.get("id") == model_name), None)
    if model is None:
        echo.error(f"Model '{model_name}' not found in service '{service_name}'.")
        raise typer.Exit(1)

    current = installed_spec(model.get("installed", False), model_name)
    fields = (model.get("spec") or {}).get("fields") or []
    version = resolve_image_version(
        image_version, bool(spec or set_args), server, api_key, service_name, current, fields, model_id=model_name
    )
    new_spec = build_updated_spec(current, spec, set_args, version)
    if new_spec == current:
        echo.info(f"Model '{model_name}' already has these settings; nothing to update.")
        return
    if not confirm_version_change(model_name, current, new_spec):
        echo.info("Update cancelled.")
        return

    url = f"{server}/admin/services/{quote_id(service_name)}/models/_/edit?model_id={quote_id(model_name)}"
    data: dict[str, Any] = cancel_on_interrupt(
        lambda: call_infra(
            lambda: install_with_progress(
                url, api_key, data={"spec": new_spec}, message=f"Updating model {model_name}..."
            ),
            "Unable to update model.",
            server=server,
            api_key=api_key,
            quiet=True,
        ),
        lambda: cancel_model_install(server, api_key, service_name, model_name),
        f"model '{model_name}'",
    )

    if str(data.get("status", "")).lower() != "ok":
        message = data.get("details")
        echo.error(f"Unable to update model.{f' {message}' if message else ''}")
        raise typer.Exit(1)

    echo.success(f"Model {model_name} updated.")
