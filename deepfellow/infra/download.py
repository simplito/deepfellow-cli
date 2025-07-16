"""Download module typer command."""

import typer

app = typer.Typer()


@app.command()
def download(model: str) -> None:
    """Download model."""
    print(f"Infra download {model}")
