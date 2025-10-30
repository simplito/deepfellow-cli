"""server organization get command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.server.organization.utils import get_organization
from deepfellow.server.utils.login import get_token
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def get(
    directory: Path = directory_option("Target directory for the DeepFellow Server installation."),
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow server address"),
    organization_id: str = typer.Argument(...),
) -> None:
    """Display organization info."""
    # Get token for the server
    secrets_file = directory / ".secrets"
    token = get_token(secrets_file, server, None)

    organization = get_organization(server, organization_id, token)

    # Response

    echo.info(str(organization))
