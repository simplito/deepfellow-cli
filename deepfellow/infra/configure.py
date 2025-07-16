"""Configure server typer command."""

import typer

from deepfellow.common.config import get_config

app = typer.Typer()


@app.command()
def configure(ctx: typer.Context) -> None:
    """Configure infra."""
    config = get_config(ctx)
    typer.echo(f"Infra configure using config: {config}")
    print("Configuring infra")
    print("Ask for admin API Key, or create a new one.")
