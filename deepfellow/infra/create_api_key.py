"""Create API Key typer command."""

import typer

from deepfellow.common.config import get_config_path
from deepfellow.common.echo import echo

app = typer.Typer()


@app.command()
def create_api_key(ctx: typer.Context) -> None:
    """Create API Key infra."""
    config = get_config_path(ctx)
    typer.echo(f"Infra create-api-key using config: {config}")
    echo.info("Creating API Key for infra")
