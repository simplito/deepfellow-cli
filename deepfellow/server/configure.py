"""Configure server typer command."""

import typer

from deepfellow.common.config import get_config_path

app = typer.Typer()


@app.command()
def configure(ctx: typer.Context) -> None:
    """Configure server."""
    config = get_config_path(ctx)
    typer.echo(f"Server configure using config: {config}")
    print("Configuring server")
    print("Ask for admin API Key, or create a new one.")
    print("Retrive info about access to infra, database.")
