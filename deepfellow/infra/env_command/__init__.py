"""Collect infra env commands."""

import typer

from .set import app as set_app

app = typer.Typer()


app.add_typer(set_app)
