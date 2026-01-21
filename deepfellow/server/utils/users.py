# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Server admin util."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.system import run
from deepfellow.common.validation import validate_email, validate_password, validate_truthy


class UserActionError(Exception):
    """Raised if create exception failes on docker."""


def create_admin(directory: Path, name: str | None, email: str | None, password: str | None) -> None:
    """Create admin."""
    name = name or echo.prompt_until_valid("Provide admin name", validate_truthy)
    email = email or echo.prompt_until_valid("Provide admin email", validate_email)
    password = password or echo.prompt("Provide admin password", validate_password, password=True)

    response: str | None = None
    try:
        response = run(
            (
                [
                    "docker",
                    "compose",
                    "run",
                    "--rm",
                    "server",
                    "./.venv/bin/python",
                    "-m",
                    "server.scripts.create_admin",
                    str(name),
                    str(email),
                    str(password),
                ]
            ),
            cwd=directory,
            raises=UserActionError,
            capture_output=True,
        )
    except UserActionError as exc:
        if "User with that email already exists" in str(exc):
            echo.error("Unable to create an admin: user with that email already exists")
        else:
            echo.error("Unable to create an admin.")
        raise typer.Exit(1) from exc

    if response and "Admin created" in response:
        echo.success("Admin account created.")


def reset_password(directory: Path, email: str | None, password: str | None) -> None:
    """Reset password."""
    email = email or echo.prompt_until_valid("Provide admin email", validate_email)
    password = password or echo.prompt_until_valid("Provide admin password", validate_password, password=True)

    response: str | None = None
    try:
        response = run(
            (
                [
                    "docker",
                    "compose",
                    "run",
                    "--rm",
                    "server",
                    "./.venv/bin/python",
                    "-m",
                    "server.scripts.set_password",
                    str(email),
                    str(password),
                ]
            ),
            cwd=directory,
            raises=UserActionError,
            capture_output=True,
        )
    except UserActionError as exc:
        if "User not found" in str(exc):
            echo.error("Unable to set password: User not found.")
        else:
            echo.error("Unable to set password.")
        raise typer.Exit(1) from exc

    if response and "Password changed" in response:
        echo.success("Password changed.")
