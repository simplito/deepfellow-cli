# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""server nightshift reconcile typer command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.server.utils.docker import reconcile_nightshift_running_state, wait_for_docker
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()

DOCKER_WAIT_SECONDS = 300
SERVER_WAIT_SECONDS = 120


@app.command(hidden=True)
def reconcile(
    directory: Path = directory_option("Target directory for the server installation.", exists=True),
) -> None:
    """Start or stop the Nightshift worker to match its schedule right now (run by the systemd timers).

    Both timers run this same command, so a replayed (`Persistent=true`) missed trigger can never
    leave the worker in the wrong state, whichever order they fire in: it checks the current time
    against the configured window instead of blindly starting or stopping. Waits for Docker first -
    right after boot the timer can fire before the daemon is up - and never starts the worker
    unless this install's `server` is running, giving Docker's restart policy up to
    SERVER_WAIT_SECONDS to bring it back after boot.
    """
    check_server_directory(directory)
    if not wait_for_docker(DOCKER_WAIT_SECONDS):
        echo.error(f"Docker did not become available within {DOCKER_WAIT_SECONDS} seconds.")
        raise typer.Exit(1)
    assert_docker()
    reconcile_nightshift_running_state(directory, server_wait_seconds=SERVER_WAIT_SECONDS)
