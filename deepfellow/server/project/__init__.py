"""Collect server project commands."""

import typer

from .archive import app as archive_app
from .create import app as create_app
from .get import app as get_app
from .list import app as list_app

app = typer.Typer()


app.add_typer(get_app)
app.add_typer(list_app)
app.add_typer(create_app)
app.add_typer(archive_app)
