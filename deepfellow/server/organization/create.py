"""server organization create command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.validation import validate_server
from deepfellow.server.organization.utils import create_organization
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def create(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Server address"),
    name: str = typer.Argument(...),
) -> None:
    """Create organization."""
    # Get token for the server
    secrets_file = ctx.obj.get("cli-secrets-file")
    server = get_server_url(server)
    token = get_token(secrets_file, server, None)

    organization = create_organization(server, token, name)

    echo.info(str(organization))
