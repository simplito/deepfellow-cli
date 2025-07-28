"""Start infra typer command."""

import typer

from deepfellow.common.config import get_config_path
from deepfellow.common.echo import echo

app = typer.Typer()


@app.command()
def start(ctx: typer.Context) -> None:
    """Start infra."""
    config = get_config_path(ctx)
    typer.echo(f"Infra start using config: {config}")
    echo.info("Starting infra")
