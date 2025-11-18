"""server project get command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.validation import validate_server
from deepfellow.server.project.utils import get_project
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def get(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Server address"),
    organization_id: str = typer.Argument(...),
    project_id: str = typer.Argument(...),
) -> None:
    """Display Project info."""
    secrets_file = ctx.obj.get("cli-secrets-file")
    server = get_server_url(server)
    token = get_token(secrets_file, server, None)

    project = get_project(server, token, organization_id, project_id)

    echo.info(str(project))
