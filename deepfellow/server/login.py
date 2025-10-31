"""Login command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_email, validate_server
from deepfellow.server.utils.login import get_token_from_login
from deepfellow.server.utils.rest import get_server_url

app = typer.Typer()


@app.command()
def login(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Server address"),
    email: str | None = typer.Option(None, callback=validate_email, help="User email"),
) -> None:
    """Login user and store the token in the secrets file.

    Raises:
        typer.Exit if invalid credentials.
    """
    secrets_file = ctx.obj.get("cli-secrets-file")
    server = get_server_url(server)
    get_token_from_login(secrets_file, server, email)
    echo.info("Your token is stored and will be used automatically.")
