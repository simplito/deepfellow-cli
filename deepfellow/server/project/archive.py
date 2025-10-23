"""server project archive command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.server.project.utils import archive_project
from deepfellow.server.utils.login import get_token
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def archive(
    directory: Path = directory_option("Target directory for the DFServer installation."),
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow server address"),
    organization_id: str = typer.Argument(...),
    project_id: str = typer.Argument(...),
) -> None:
    """Display project info."""
    secrets_file = directory / ".secrets"
    token = get_token(secrets_file, server, None)

    project = archive_project(server, token, organization_id, project_id)

    echo.info(str(project))
