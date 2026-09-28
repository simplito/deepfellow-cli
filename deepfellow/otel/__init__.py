# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Collect otel commands."""

import typer

from .logs import app as logs_app

app = typer.Typer(no_args_is_help=True)

app.add_typer(logs_app)
