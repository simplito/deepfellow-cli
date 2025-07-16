"""Install infra typer command."""

import typer

app = typer.Typer()


@app.command()
def install() -> None:
    """Install infra."""
    print("Installing infra")
