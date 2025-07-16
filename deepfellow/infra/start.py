"""Start infra typer command."""

import typer

from deepfellow.common.config import get_config

app = typer.Typer()


@app.command()
def start(ctx: typer.Context) -> None:
    """Start infra."""
    config = get_config(ctx)
    typer.echo(f"Infra start using config: {config}")
    print("Starting infra")
