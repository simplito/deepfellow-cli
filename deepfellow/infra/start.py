"""Start infra typer command."""

from pathlib import Path

import typer

from deepfellow.common.defaults import DF_INFRA_DIRECTORY
from deepfellow.common.echo import echo
from deepfellow.common.system import run
from deepfellow.common.validation import validate_directory

app = typer.Typer()


@app.command()
def start(
    directory: Path = typer.Option(
        DF_INFRA_DIRECTORY,
        "--directory",
        "--dir",
        envvar="DF_INFRA_DIRECTORY",
        help="Target directory for the Infra installation.",
        callback=validate_directory,
    ),
) -> None:
    """Start infra."""
    echo.info("Starting DF Infra")
    run("docker compose up -d", cwd=directory)
