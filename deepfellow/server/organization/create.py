"""server organization create command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.server.organization.utils import create_organization
from deepfellow.server.utils.login import get_token
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def create(
    directory: Path = directory_option("Target directory for the DeepFellow Server installation."),
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow server address"),
    name: str = typer.Argument(...),
) -> None:
    """Create organization."""
    # Get token for the server
    secrets_file = directory / ".secrets"
    token = get_token(secrets_file, server, None)

    organization = create_organization(server, token, name)

    echo.info(str(organization))
