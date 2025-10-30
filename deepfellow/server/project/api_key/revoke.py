"""server project api-key create command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.server.project.api_key.utils import delete_api_key, get_api_key
from deepfellow.server.utils.login import get_token
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def revoke(
    ctx: typer.Context,
    directory: Path = directory_option("Target directory for the DeepFellow Server installation."),
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow server address"),
    organization_id: str = typer.Argument(..., help="Organization ID to add the API Key"),
    project_id: str = typer.Argument(..., help="Organization ID to add the API Key"),
    api_key_id: str = typer.Argument(..., help="Organization API Key to revoke"),
) -> None:
    """Revoke project API Key."""
    yes = ctx.obj.get("yes", False)
    if yes:
        echo.debug("Automatically confirming the revoke.")

    secrets_file = directory / ".secrets"
    token = get_token(secrets_file, server, None)

    api_key = get_api_key(server, token, organization_id, project_id, api_key_id)

    if not yes and not echo.confirm(
        f"Are you sure you want to delete the Project API Key {api_key.name}?", default=False
    ):
        raise typer.Exit(1)

    delete_api_key(server, token, organization_id, project_id, api_key_id)

    echo.info("API Key revoked.")
