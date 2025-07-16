"""Start infra typer command."""

import typer

app = typer.Typer()


@app.command()
def start() -> None:
    """Start infra."""
    print("Starting infra")
