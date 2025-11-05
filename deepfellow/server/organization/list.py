"""server organization list command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.server.organization.utils import list_organizations
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def list(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Server address"),
) -> None:
    """Display list of organizations."""
    # Get token for the server
    secrets_file = ctx.obj.get("cli-secrets-file")
    token = get_token(secrets_file, server, None)

    organizations = list_organizations(server, token)
    echo.info("\n\n".join([str(org) for org in organizations]))
