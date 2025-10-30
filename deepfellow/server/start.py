"""Start server typer command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.system import run
from deepfellow.common.validation import validate_directory
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def start(
    directory: Path = directory_option(
        "Target directory for the server installation.",
        callback=validate_directory,
    ),
) -> None:
    """Start DeepFellow Server."""
    echo.info("Starting DeepFellow Server")
    run("docker compose up -d", cwd=directory)
    echo.info("DeepFellow Server started.")
