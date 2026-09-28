# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Collect server dynamic config commands."""

import typer

from .get import app as get_app
from .set import app as set_app

app = typer.Typer(no_args_is_help=True)

app.add_typer(get_app)
app.add_typer(set_app)
