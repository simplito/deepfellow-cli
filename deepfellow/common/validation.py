"""Common validations."""

import typer

from .echo import echo
from .system import is_command_available

REQUIRED_COMMANDS = ("uv",)


def validate_system() -> None:
    """Validate if the system has all dependencies."""
    failed_commands = []
    # TODO Validate for Python verdion
    echo.debug("TODO - Implement Python version validation.")
    for command in REQUIRED_COMMANDS:
        if not is_command_available(command):
            failed_commands.append(command)

    if failed_commands:
        echo.error("System is not ready for DeepFellow.")
        echo.error("\n".join(f"Please install `{command}` command" for command in failed_commands))
        raise typer.Exit(1)
