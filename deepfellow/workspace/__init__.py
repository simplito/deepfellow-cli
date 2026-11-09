# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Collect workspace commands."""

import typer

from .install import app as install_app
from .uninstall import app as uninstall_app

app = typer.Typer(no_args_is_help=True)

app.add_typer(install_app)
app.add_typer(uninstall_app)
