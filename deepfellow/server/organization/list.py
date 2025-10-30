"""server organization list command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.server.organization.utils import list_organizations
from deepfellow.server.utils.login import get_token
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def list(
    directory: Path = directory_option("Target directory for the DeepFellow Server installation."),
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow server address"),
) -> None:
    """Display list of organizations."""
    # Get token for the server
    secrets_file = directory / ".secrets"
    token = get_token(secrets_file, server, None)

    organizations = list_organizations(server, token)
    echo.info("\n\n".join([str(org) for org in organizations]))
