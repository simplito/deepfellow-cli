"""Install infra typer command."""

import typer

from deepfellow.common.echo import echo

app = typer.Typer()


@app.command()
def install() -> None:
    """Install infra."""
    echo.info("Installing infra")
