# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Collect infra env commands."""

import typer

from .info import app as info_app
from .set import app as set_app

app = typer.Typer(no_args_is_help=True)


app.add_typer(set_app)
app.add_typer(info_app)
