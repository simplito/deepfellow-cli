"""Create admin command."""

from pathlib import Path

import typer

from deepfellow.common.validation import validate_email
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.users import create_admin as create_admin_util

app = typer.Typer()


@app.command()
def create_admin(
    directory: Path = directory_option("Target directory for the DFServer installation."),
    email: str | None = typer.Option(None, callback=validate_email, help="Admin email"),
    password: str | None = typer.Option(None, help="Admin password"),
) -> None:
    """Create admin.

    Returns:
        token string
    """
    create_admin_util(directory, email, password)
