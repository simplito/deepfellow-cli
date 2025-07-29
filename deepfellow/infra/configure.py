"""Configure server typer command."""

import typer

from deepfellow.common.config import get_config_path
from deepfellow.common.echo import echo

app = typer.Typer()


@app.command()
def configure() -> None:
    """Configure infra."""
    config = get_config_path()
    typer.echo(f"Infra configure using config: {config}")
    echo.info("Configuring infra")
    echo.info("Ask for admin API Key, or create a new one.")
