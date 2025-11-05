"""server organization api-key create command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.server.organization.admin_api_key.utils import delete_admin_api_key, get_admin_api_key
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def revoke(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Server address"),
    organization_id: str = typer.Argument(..., help="Organization ID to add the API Key"),
    api_key_id: str = typer.Argument(..., help="Organization API Key to revoke"),
) -> None:
    """Revoke organization API Key."""
    yes = ctx.obj.get("yes", False)
    if yes:
        echo.debug("Automatically confirming the revoke.")

    secrets_file = ctx.obj.get("cli-secrets-file")
    token = get_token(secrets_file, server, None)

    api_key = get_admin_api_key(server, token, organization_id, api_key_id)

    if not yes and not echo.confirm(
        f"Are you sure you want to delete the Organization API Key {api_key.name}?", default=False
    ):
        raise typer.Exit(1)

    delete_admin_api_key(server, token, organization_id, api_key_id)

    echo.info("API Key revoked.")
