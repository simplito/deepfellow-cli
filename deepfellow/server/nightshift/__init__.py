# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Collect server nightshift commands.

Configuration/visibility only - there is no install/on/off subcommand here, since RabbitMQ and the
Nightshift worker are always provisioned by `server install`/`suite install` (see
`deepfellow.server.utils.configure.configure_nightshift`).
"""

import typer

from .mode import app as mode_app
from .queue import app as queue_app
from .reconcile import app as reconcile_app
from .restart import app as restart_app
from .schedule import app as schedule_app
from .start import app as start_app
from .status import app as status_app
from .stop import app as stop_app

app = typer.Typer(no_args_is_help=True)


app.add_typer(start_app)
app.add_typer(stop_app)
app.add_typer(restart_app)
app.add_typer(status_app)
app.add_typer(mode_app)
app.add_typer(schedule_app)
app.add_typer(queue_app)
app.add_typer(reconcile_app)
