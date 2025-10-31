"""Common validations."""

from pathlib import Path
from typing import cast
from urllib.parse import urlparse

import typer
from email_validator import EmailNotValidError
from email_validator import validate_email as validate_email_lib
from typer import BadParameter

from .echo import echo
from .system import is_command_available

REQUIRED_COMMANDS = ("uv",)


def validate_system() -> None:
    """Validate if the system has all dependencies."""
    failed_commands = []
    # TODO Validate for Python version
    echo.debug("TODO - Implement Python version validation.")
    for command in REQUIRED_COMMANDS:
        if not is_command_available(command):
            failed_commands.append(command)

    if failed_commands:
        echo.error("System is not ready for DeepFellow.")
        echo.error("\n".join(f"Please install `{command}` command" for command in failed_commands))
        raise typer.Exit(1)


def validate_directory(directory: str | Path | None) -> Path:
    """Raise an error if directory argument is not an existing directory."""
    if isinstance(directory, str):
        directory = Path(directory)

    if directory is None or not directory.is_dir():
        raise BadParameter(f"Directory {directory} does not exist")

    return directory


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
