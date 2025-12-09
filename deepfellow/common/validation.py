# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Common validations."""

import re
from typing import Any, cast
from urllib.parse import urlparse

import typer
from email_validator import EmailNotValidError
from email_validator import validate_email as validate_email_lib

from .echo import echo
from .system import is_command_available

REQUIRED_COMMANDS = ("uv",)
USERNAME_REGEX = r"^[a-zA-Z][a-zA-Z0-9_]{2,19}$"
PASSWORD_REGEX = r"^[a-zA-Z0-9_!@#$%^&*()_=+\-]{8,19}$"


def validate_system() -> None:
    """Validate if the system has all dependencies."""
    failed_commands = []
    # TODO Validate for Python version
    for command in REQUIRED_COMMANDS:
        if not is_command_available(command):
            failed_commands.append(command)

    if failed_commands:
        echo.error("System is not ready for DeepFellow.")
        echo.error("\n".join(f"Please install `{command}` command" for command in failed_commands))
        raise typer.Exit(1)


def validate_email(value: str | None) -> str | None:
    """Validate srting is an email."""
    if value is None:
        # We allow email collected via option to be None
        return None

    try:
        validated = validate_email_lib(value)

    except EmailNotValidError as exc:
        raise typer.BadParameter("Invalid email address") from exc

    return validated.email


def validate_url(value: str | None) -> str | None:
    """Validate the URL entry."""
    if value is None:
        return None

    try:
        result = urlparse(value)
    except Exception as exc:
        raise typer.BadParameter("Invalid URL") from exc

    if not all([result.scheme, result.netloc]):
        raise typer.BadParameter("Invalid URL - must include scheme and domain")

    return value


def validate_server(value: str | None) -> str | None:
    """Validate the server entry. Strip the last slash."""
    if value is None:
        return None

    return cast("str", validate_url(value)).rstrip("/")


def validate_df_name(value: str | None) -> str | None:
    """Validate the value for DF_NAME env. It must be non-empty string."""
    if not value:
        raise typer.BadParameter("Invalid DF_NAME - cannot be empty")

    if not isinstance(value, str):
        raise typer.BadParameter("Invalid DF_NAME - must be str")

    return value


def validate_truthy(value: Any) -> Any:
    """Validate the value is not None."""
    if not value:
        raise typer.BadParameter("Value can't be empty.")

    return value


def validate_username(value: str | None) -> str | None:
    """Validate value is a sane username."""
    if value is None:
        return None

    validate_truthy(value)
    if not re.match(USERNAME_REGEX, value):
        raise typer.BadParameter("Invalid username - only letters, numbers, and '_' are allowed.")

    return value


def validate_password(value: str | None) -> str | None:
    """Validate value is a sane password."""
    if value is None:
        return None

    if not re.match(PASSWORD_REGEX, value):
        raise typer.BadParameter("Invalid password - min 8 characters of 'a-zA-Z0-9_!@#$%^&*()_=+-'.")

    return value
