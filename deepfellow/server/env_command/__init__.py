"""Collect infra env commands."""

import typer

from .info import app as info_app
from .set import app as set_app

app = typer.Typer()


app.add_typer(set_app)
app.add_typer(info_app)
