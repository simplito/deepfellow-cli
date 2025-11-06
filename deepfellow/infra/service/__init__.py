"""Collect infra env commands."""

import typer

from .install import app as install_app
from .uninstall import app as uninstall_app

app = typer.Typer()


app.add_typer(install_app)
app.add_typer(uninstall_app)
