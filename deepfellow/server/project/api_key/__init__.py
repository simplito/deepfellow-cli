"""Collect server project api-key commands."""

import typer

from .create import app as create_app
from .revoke import app as revoke_app

app = typer.Typer()


app.add_typer(create_app)
app.add_typer(revoke_app)
