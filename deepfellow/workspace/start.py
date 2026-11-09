# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Start workspace typer command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.workspace.utils.docker import confirm_server_running, start_workspace, workspace_url
from deepfellow.workspace.utils.options import directory_option
from deepfellow.workspace.utils.validation import check_workspace_directory

app = typer.Typer()


@app.command()
def start(directory: Path = directory_option("DeepFellow Workspace directory.", exists=True)) -> None:
    """Start DeepFellow Workspace."""
    check_workspace_directory(directory)
    assert_docker()
    confirm_server_running(directory)
    start_workspace(directory)
    echo.info(f"DeepFellow Workspace started on {workspace_url(directory)}")
