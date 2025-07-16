"""Install server typer command."""

import typer

app = typer.Typer()


@app.command()
def install() -> None:
    """Install server."""
    print("Installing server")
