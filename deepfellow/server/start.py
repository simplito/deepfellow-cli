"""Start server typer command."""

import typer

app = typer.Typer()


@app.command()
def start() -> None:
    """Start server."""
    print("Starting server")
