# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Collect cli commands."""

import typer

from .uninstall import app as uninstall_app
from .update import app as update_app

app = typer.Typer(no_args_is_help=True)

app.add_typer(uninstall_app)
app.add_typer(update_app)
