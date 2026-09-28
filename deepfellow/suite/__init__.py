# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Collect suite commands."""

import typer

from .install import app as install_app

app = typer.Typer(no_args_is_help=True)

app.add_typer(install_app)
