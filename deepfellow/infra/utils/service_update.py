# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Update service core logic."""

from typing import Any

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get
from deepfellow.infra.utils.connection import (
    call_infra,
    cancel_on_interrupt,
    cancel_service_install,
    quote_id,
    resolve_infra_connection,
)
from deepfellow.infra.utils.progress import install_with_progress
from deepfellow.infra.utils.update_spec import (
    build_updated_spec,
    confirm_version_change,
    installed_spec,
    resolve_image_version,
)


def update(
    name: str,
    server: str | None = None,
    spec: str | None = None,
    set_args: list[str] | None = None,
    image_version: str | None = None,
) -> None:
    """Change the settings of an installed service, for example its Docker image tag.

    Infra recreates the service's container and reinstalls the previous settings if that fails.

    Args:
        name: Service name (e.g. "ollama", or "ollama|cpu" for an instance).
        server: Infra server URL. Resolved from config/prompt if not given.
        spec: JSON object with the changed settings.
        set_args: `key=value` overrides of individual settings.
        image_version: Docker image tag to move the service to. The newest release when neither this nor
            other changes are given.
    """
    server, api_key = resolve_infra_connection(server)
    url = f"{server}/admin/services/{quote_id(name)}"

    service = call_infra(
        lambda: get(url, api_key, item_name="Service", reraise=True),
        f"Unable to fetch service '{name}'.",
        server=server,
        api_key=api_key,
        quiet=True,
    )
    current = installed_spec(service.get("installed", False), name)
    fields = (service.get("spec") or {}).get("fields") or []
    version = resolve_image_version(image_version, bool(spec or set_args), server, api_key, name, current, fields)
    new_spec = build_updated_spec(current, spec, set_args, version)
    if new_spec == current:
        echo.info(f"Service '{name}' already has these settings; nothing to update.")
        return
    if not confirm_version_change(name, current, new_spec):
        echo.info("Update cancelled.")
        return

    err_msg = "Unable to update service."
    data: dict[str, Any] = cancel_on_interrupt(
        lambda: call_infra(
            lambda: install_with_progress(
                url, api_key, data={"spec": new_spec}, message=f"Updating service {name}...", method="PUT"
            ),
            err_msg,
            server=server,
            api_key=api_key,
            quiet=True,
        ),
        lambda: cancel_service_install(server, api_key, name),
        f"service '{name}'",
    )

    if str(data.get("status", "")).lower() != "ok":
        message = data.get("details")
        echo.error(f"{err_msg}{f' {message}' if message else ''}")
        raise typer.Exit(1)

    echo.success(f"Service {name} updated.")
