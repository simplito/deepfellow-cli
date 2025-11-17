"""Server and infra install util."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug


def ensure_directory(
    directory: Path,
    warning_message: str | None = None,
    confirm_message: str | None = None,
    error_message: str | None = None,
) -> None:
    """Check if overriding the existing installation and create directory if needed."""
    confirm_message = confirm_message or "Should I override existing installation?"
    error_message = error_message or f"Unable to create directory {directory}."
    warning_message = warning_message or f"Directory {directory} already exists."

    directory_exists = False
    if directory.is_dir():
        echo.warning(warning_message)
        if not echo.confirm(confirm_message):
            raise typer.Exit(1)

        directory_exists = True

    if not directory_exists:
        try:
            directory.mkdir(parents=True)
        except Exception as exc_info:
            echo.error(error_message)
            reraise_if_debug(exc_info)
