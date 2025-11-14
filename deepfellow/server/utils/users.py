"""Server admin util."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.system import run
from deepfellow.common.validation import validate_email


class CreateAdminError(Exception):
    """Raised if create exception failes on docker."""


def create_admin(directory: Path, name: str | None, email: str | None, password: str | None) -> None:
    """Create admin."""
    name = name or echo.prompt("Provide admin name")
    email = email or echo.prompt("Provide admin email", validation=validate_email)
    password = password or echo.prompt("Provide admin password", password=True)

    response: str | None = None
    try:
        response = run(
            (
                "docker compose run --rm server ./.venv/bin/python -m server.scripts.create_admin "
                f"{name} {email} {password}"
            ),
            cwd=directory,
            raises=CreateAdminError,
            capture_output=True,
        )
    except CreateAdminError as exc:
        if "User with that email already exists" in str(exc):
            echo.error("Unable to create an admin: user with that email already exists")
        else:
            echo.error("Unable to create an admin.")
        raise typer.Exit(1) from exc

    if response == "Admin created\n":
        echo.info("Admin account created.")
