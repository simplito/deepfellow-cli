import typer

from .infra import app as infra_app
from .server import app as server_app

app = typer.Typer()

# Add object-based command groups
app.add_typer(infra_app, name="infra")
app.add_typer(server_app, name="server")

if __name__ == "__main__":
    app()
