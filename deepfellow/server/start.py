"""Start server typer command."""

import typer

from deepfellow.common.config import get_config_path
from deepfellow.common.echo import echo

app = typer.Typer()


@app.command()
def start() -> None:
    """Start server."""
    config = get_config_path()
    typer.echo(f"Server start using config: {config}")
    echo.info("Starting server")
