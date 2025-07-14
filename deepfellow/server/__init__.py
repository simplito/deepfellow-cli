import typer

from .install import app as install_app

app = typer.Typer()
app.add_typer(install_app)
