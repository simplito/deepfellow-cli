"""server project create command."""

from enum import Enum

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.validation import validate_server
from deepfellow.server.project.utils import create_project
from deepfellow.server.utils.login import get_token

app = typer.Typer()


class Status(str, Enum):
    active = "active"
    archived = "archived"


@app.command()
def create(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Server address"),
    organization_id: str = typer.Argument(...),
    name: str = typer.Argument(...),
    status: Status = typer.Option(Status.active, help="Status of the Project"),
    models: list[str] | None = typer.Option(None, help="List of models this Project can use. 'all' or list of models"),
    custom_endpoints: list[str] = typer.Option([], help="List of custom endpoints"),
) -> None:
    """Create organization."""
    # Get token for the server
    secrets_file = ctx.obj.get("cli-secrets-file")
    server = get_server_url(server)
    token = get_token(secrets_file, server, None)

    # Determine actual models value
    if models and "all" in models and len(models) > 1:
        raise typer.BadParameter("Cannot mix 'all' with specific models")

    project_models: str | list[str] = "all"
    if models and models != ["all"]:
        project_models = models

    project = create_project(
        server,
        token,
        organization_id,
        {
            "name": name,
            "status": status,
            "models": project_models,
            "custom_endpoints": custom_endpoints,
        },
    )

    echo.info(str(project))
