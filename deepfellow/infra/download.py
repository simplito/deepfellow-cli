"""Download module typer command."""

import typer

from deepfellow.common.config import get_config

app = typer.Typer()


@app.command()
def download(ctx: typer.Context, model: str) -> None:
    """Download model."""
    config = get_config(ctx)
    typer.echo(f"Infra download using config: {config}")
    print(f"Infra download {model}")
