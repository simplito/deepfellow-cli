# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Collect server tool commands."""

import typer

from .create import app as create_app
from .delete import app as delete_app
from .get import app as get_app
from .list import app as list_app
from .update import app as update_app

app = typer.Typer(no_args_is_help=True)

app.add_typer(get_app)
app.add_typer(list_app)
app.add_typer(create_app)
app.add_typer(update_app)
app.add_typer(delete_app)
