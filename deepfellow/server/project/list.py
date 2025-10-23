"""server project list command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.server.project.utils import list_projects
from deepfellow.server.utils.login import get_token
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def list(
    directory: Path = directory_option("Target directory for the DFServer installation."),
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow server address"),
    organization_id: str = typer.Argument(...),
) -> None:
    """Display list of projects."""
    # Get token for the server
    secrets_file = directory / ".secrets"
    token = get_token(secrets_file, server, None)

    projects = list_projects(server, token, organization_id)
    echo.info("\n\n".join([str(org) for org in projects]))
