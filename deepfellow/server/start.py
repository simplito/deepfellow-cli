"""Start server typer command."""

import typer

from deepfellow.common.config import get_config

app = typer.Typer()


@app.command()
def start(ctx: typer.Context) -> None:
    """Start server."""
    config = get_config(ctx)
    typer.echo(f"Server start using config: {config}")
    print("Starting server")
