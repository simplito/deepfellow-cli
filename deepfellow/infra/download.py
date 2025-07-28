"""Download module typer command."""

import typer

from deepfellow.common.config import get_config_path
from deepfellow.common.echo import echo

app = typer.Typer()


@app.command()
def download(ctx: typer.Context, model: str) -> None:
    """Download model."""
    config = get_config_path(ctx)
    typer.echo(f"Infra download using config: {config}")
    echo.info(f"Infra download {model}")
