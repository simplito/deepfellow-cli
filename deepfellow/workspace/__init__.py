# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Collect workspace commands."""

import typer

from .env_command import app as env_app
from .info import app as info_app
from .install import app as install_app
from .logs import app as logs_app
from .restart import app as restart_app
from .start import app as start_app
from .status import app as status_app
from .stop import app as stop_app
from .uninstall import app as uninstall_app
from .update import app as update_app

app = typer.Typer(no_args_is_help=True)

app.add_typer(install_app)
app.add_typer(uninstall_app)
app.add_typer(start_app)
app.add_typer(stop_app)
app.add_typer(restart_app)
app.add_typer(status_app)
app.add_typer(logs_app)
app.add_typer(update_app)
app.add_typer(info_app)
app.add_typer(env_app, name="env", help="Manage DeepFellow Workspace settings.")
