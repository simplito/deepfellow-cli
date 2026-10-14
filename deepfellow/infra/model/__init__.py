# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Collect infra env commands."""

import typer

from .install import app as install_app
from .list import app as list_app
from .uninstall import app as uninstall_app
from .update import app as update_app
from .versions import app as versions_app

app = typer.Typer(no_args_is_help=True)


app.add_typer(install_app)
app.add_typer(list_app)
app.add_typer(uninstall_app)
app.add_typer(update_app)
app.add_typer(versions_app)
