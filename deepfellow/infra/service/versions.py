# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""infra service versions command."""

import typer

from deepfellow.common.rest import get
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.connection import call_infra, quote_id, resolve_infra_connection
from deepfellow.infra.utils.update_spec import installed_spec
from deepfellow.infra.utils.versions import show_versions

app = typer.Typer()


@app.command()
def versions(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
    name: str = typer.Argument(..., help="service name (e.g. ollama)"),
) -> None:
    """List the Docker image versions available for a service, newest first."""
    server, api_key = resolve_infra_connection(server)
    service = call_infra(
        lambda: get(f"{server}/admin/services/{quote_id(name)}", api_key, item_name="Service", reraise=True),
        f"Unable to fetch service '{name}'.",
        server=server,
        api_key=api_key,
        quiet=True,
    )
    installed = service.get("installed", False)
    current = installed_spec(installed, name) if installed is not False else None
    show_versions(server, api_key, name, current)
