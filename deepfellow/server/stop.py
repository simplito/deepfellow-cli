"""Start server typer command."""

from pathlib import Path

import typer

from deepfellow.common.defaults import DF_SERVER_DIRECTORY
from deepfellow.common.echo import echo
from deepfellow.common.system import run
from deepfellow.common.validation import validate_directory

app = typer.Typer()


@app.command()
def stop(
    directory: Path = typer.Option(
        DF_SERVER_DIRECTORY,
        "--directory",
        "--dir",
        envvar="DF_SERVER_DIRECTORY",
        help="Target directory for the Sever installation.",
        callback=validate_directory,
    ),
) -> None:
    """Start server."""
    echo.debug("Stopping DF Server")
    run("docker compose down", cwd=directory)
    echo.success("DF Server is down")
