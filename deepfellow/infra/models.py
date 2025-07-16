"""Models list typer command."""

import typer

app = typer.Typer()


@app.command()
def models() -> None:
    """Models list."""
    print("Infra list models")
