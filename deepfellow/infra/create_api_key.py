"""Create API Key typer command."""

import typer

app = typer.Typer()


@app.command()
def create_api_key() -> None:
    """Create API Key infra."""
    print("Creating API Key for infra")
