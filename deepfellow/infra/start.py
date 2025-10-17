"""Start infra typer command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.system import run
from deepfellow.common.validation import validate_directory
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def start(
    directory: Path = directory_option(
        callback=validate_directory,
    ),
) -> None:
    """Start infra."""
    echo.info("Starting DF Infra")
    run("docker compose up -d", cwd=directory)
