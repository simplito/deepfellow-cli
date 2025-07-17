"""Create API Key typer command."""

import typer

from deepfellow.common.config import get_config_path

app = typer.Typer()


@app.command()
def create_api_key(ctx: typer.Context) -> None:
    """Create API Key infra."""
    config = get_config_path(ctx)
    typer.echo(f"Infra create-api-key using config: {config}")
    print("Creating API Key for infra")
