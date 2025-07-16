import typer

from .configure import app as configure_app
from .install import app as install_app
from .start import app as start_app

app = typer.Typer()
app.add_typer(install_app)
app.add_typer(configure_app)
app.add_typer(start_app)
