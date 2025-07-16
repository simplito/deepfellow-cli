"""Create API Key typer command."""

import typer

from deepfellow.common.config import get_config

app = typer.Typer()


@app.command()
def create_api_key(ctx: typer.Context) -> None:
    """Create API Key infra."""
    config = get_config(ctx)
    typer.echo(f"Infra create-api-key using config: {config}")
    print("Creating API Key for infra")
