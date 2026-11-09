# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Workspace status typer command."""

from pathlib import Path

import typer

from deepfellow.common.defaults import WORKSPACE_APP_SERVICE
from deepfellow.common.docker import is_service_running, print_docker_status
from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.workspace.utils.options import directory_option
from deepfellow.workspace.utils.validation import check_workspace_directory

app = typer.Typer()


@app.command()
def status(directory: Path = directory_option("DeepFellow Workspace directory.", exists=True)) -> None:
    """Show DeepFellow Workspace status."""
    check_workspace_directory(directory)
    assert_docker()
    echo.debug("Showing DeepFellow Workspace status")
    if not is_service_running(WORKSPACE_APP_SERVICE, directory):
        echo.info("DeepFellow Workspace is not running. Start it with 'workspace start'.")
        return
    print_docker_status(directory, WORKSPACE_APP_SERVICE)
