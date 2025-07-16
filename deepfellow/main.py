"""Main typer module."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version

import typer

from .infra import app as infra_app
from .server import app as server_app

app = typer.Typer(invoke_without_command=True)


@app.callback()
def main(version: bool = typer.Option(False)) -> None:
    """Display callback function."""
    if version:
        try:
            typer.echo(get_version("deepfellow-cli"))
        except PackageNotFoundError:
            typer.echo("No version information available. Have you installed the command?")


# Add object-based command groups
app.add_typer(infra_app, name="infra")
app.add_typer(server_app, name="server")

if __name__ == "__main__":
    app()
