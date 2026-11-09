# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Stop workspace typer command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.workspace.utils.docker import stop_workspace
from deepfellow.workspace.utils.options import directory_option
from deepfellow.workspace.utils.validation import check_workspace_directory

app = typer.Typer()


@app.command()
def stop(directory: Path = directory_option("DeepFellow Workspace directory.", exists=True)) -> None:
    """Stop DeepFellow Workspace; its containers and data are kept."""
    check_workspace_directory(directory)
    assert_docker()
    echo.debug("Stopping DeepFellow Workspace")
    stop_workspace(directory)
    echo.success("DeepFellow Workspace is stopped.")
