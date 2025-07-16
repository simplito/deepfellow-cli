"""Models list typer command."""

import typer

from deepfellow.common.config import get_config

app = typer.Typer()


@app.command()
def models(ctx: typer.Context) -> None:
    """Models list."""
    config = get_config(ctx)
    typer.echo(f"Infra models using config: {config}")
    print("Infra list models")
