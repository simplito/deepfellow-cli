"""Collect server organization commands."""

import typer

from .create import app as create_app
from .get import app as get_app
from .list import app as list_app

app = typer.Typer()


app.add_typer(create_app)
app.add_typer(list_app)
app.add_typer(get_app)
# Temporarily disabling the delete organization.
# from .delete import app as delete_app
# app.add_typer(delete_app)
