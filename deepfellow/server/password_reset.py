"""Reset password command."""

from pathlib import Path

import typer

from deepfellow.common.validation import validate_email
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.users import reset_password as reset_password_util

app = typer.Typer()


@app.command()
def password_reset(
    directory: Path = directory_option("Target directory for the DeepFellow Server installation."),
    email: str | None = typer.Argument(None, callback=validate_email, help="Email"),
    password: str | None = typer.Option(None, help="Password"),
) -> None:
    """Password reset."""
    reset_password_util(directory, email, password)
