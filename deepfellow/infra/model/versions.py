# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""infra model versions command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.connection import resolve_infra_connection
from deepfellow.infra.utils.models import get_service_models
from deepfellow.infra.utils.update_spec import installed_spec
from deepfellow.infra.utils.versions import show_versions

app = typer.Typer()


@app.command()
def versions(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
    service_name: str = typer.Argument(..., help="service name (e.g. custom)"),
    model_name: str = typer.Argument(..., help="model name (e.g. doc_chunker)"),
) -> None:
    """List the Docker image versions available for a model, newest first."""
    server, api_key = resolve_infra_connection(server)
    models = get_service_models(server, api_key, service_name, quiet=True)
    model = next((item for item in models if item.get("id") == model_name), None)
    if model is None:
        echo.error(f"Model '{model_name}' not found in service '{service_name}'.")
        raise typer.Exit(1)
    installed = model.get("installed", False)
    current = installed_spec(installed, model_name) if installed is not False else None
    show_versions(server, api_key, service_name, current, model_id=model_name)
