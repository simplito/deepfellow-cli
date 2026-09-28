# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Collect server project api-key commands."""

import typer

from .create import app as create_app
from .revoke import app as revoke_app

app = typer.Typer(no_args_is_help=True)


app.add_typer(create_app)
app.add_typer(revoke_app)
