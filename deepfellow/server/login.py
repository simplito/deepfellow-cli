"""Login command."""

from pathlib import Path

import typer

from deepfellow.common.validation import validate_email, validate_url
from deepfellow.server.utils.login import get_token_from_login
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def login(
    directory: Path = directory_option("Target directory for the DFServer installation."),
    server: str | None = typer.Option(None, callback=validate_url, help="DeepFellow server address"),
    email: str | None = typer.Option(None, callback=validate_email, help="User email"),
) -> str:
    """Login user and return the token.

    Returns:
        token string

    Raises:
        typer.Exit if invalid credentials.
    """
    secrets_file = directory / ".secrets"
    return get_token_from_login(secrets_file, server, email)
