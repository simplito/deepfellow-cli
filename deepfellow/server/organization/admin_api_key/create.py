"""server organization api-key create command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.server.organization.admin_api_key.utils import create_admin_api_key
from deepfellow.server.utils.login import get_token
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def create(
    directory: Path = directory_option("Target directory for the DeepFellow Server installation."),
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow server address"),
    organization_id: str = typer.Argument(..., help="Organization ID to add the API Key"),
    name: str = typer.Argument(..., help="Name of the API Key"),
) -> None:
    """Create organization."""
    secrets_file = directory / ".secrets"
    token = get_token(secrets_file, server, None)

    api_key = create_admin_api_key(server, token, organization_id, name)

    echo.info(str(api_key))
