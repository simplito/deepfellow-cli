"""Start infra typer command."""

from pathlib import Path

import typer

from deepfellow.common.defaults import DF_INFRA_DIRECTORY
from deepfellow.common.echo import echo
from deepfellow.common.system import run

app = typer.Typer()


@app.command()
def stop(
    directory: Path = typer.Option(
        DF_INFRA_DIRECTORY, envvar="DF_INFRA_DIRECTORY", help="Target directory for the Infra installation."
    ),
) -> None:
    """Start infra."""
    echo.debug("Stopping DF Infra")
    run("docker compose down", cwd=directory)
    echo.info("DF Infra is down")
