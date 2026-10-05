# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""server nightshift start typer command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.server.utils.docker import assert_nightshift_installed, service_running_or_exit, start_nightshift
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


@app.command()
def start(
    directory: Path = directory_option("Target directory for the server installation.", exists=True),
) -> None:
    """Start only the Nightshift worker container, not its dependencies; fails if the server isn't running."""
    check_server_directory(directory)
    assert_docker()
    assert_nightshift_installed(directory)
    if not service_running_or_exit("server", directory):
        echo.warning("The server isn't running - start it first with `deepfellow server start`.")
        raise typer.Exit(1)
    echo.info("Starting DeepFellow Nightshift worker")
    start_nightshift(directory)
    echo.success("DeepFellow Nightshift worker started.")
