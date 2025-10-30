"""Configure server typer command."""

import typer

from deepfellow.common.config import get_config_path
from deepfellow.common.echo import echo

app = typer.Typer()


@app.command()
def configure() -> None:
    """Configure server."""
    config = get_config_path()
    typer.echo(f"Deepfellow Server configure using config: {config}")
    echo.info("Configuring Deepfellow Server")
    echo.info("Ask for admin API Key, or create a new one.")
    echo.info("Retrive info about access to DeepFellow Infra, database.")
