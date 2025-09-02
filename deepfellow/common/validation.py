"""Common validations."""

from pathlib import Path

import typer
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
