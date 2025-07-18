"""Configure server typer command."""

import typer

from deepfellow.common.config import get_config_path

app = typer.Typer()


@app.command()
def configure(ctx: typer.Context) -> None:
    """Configure infra."""
    config = get_config_path(ctx)
    typer.echo(f"Infra configure using config: {config}")
    print("Configuring infra")
    print("Ask for admin API Key, or create a new one.")
