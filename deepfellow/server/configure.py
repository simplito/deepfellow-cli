"""Configure server typer command."""

import typer

app = typer.Typer()


@app.command()
def configure() -> None:
    """Configure server."""
    print("Configuring server")
    print("Ask for admin API Key, or create a new one.")
    print("Retrie info about access to infra, database.")
