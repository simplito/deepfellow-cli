# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Collect cli commands."""

import typer

from deepfellow.common.update_check import check_for_update

from .uninstall import app as uninstall_app
from .update import app as update_app

app = typer.Typer(no_args_is_help=True)


@app.callback()
def callback(ctx: typer.Context) -> None:
    """Run the newer-version check for every `cli` subcommand except `update`."""
    # The root callback skips the whole `cli` group: only here is the nested command name known.
    if ctx.invoked_subcommand != "update":
        check_for_update()


app.add_typer(uninstall_app)
app.add_typer(update_app)
