"""Models list typer command."""

import typer

from deepfellow.common.config import get_config_path

app = typer.Typer()


@app.command()
def models(ctx: typer.Context) -> None:
    """Models list."""
    config = get_config_path(ctx)
    typer.echo(f"Infra models using config: {config}")
    print("Infra list models")
