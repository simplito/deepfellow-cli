# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Workspace logs typer command."""

from pathlib import Path

import typer

from deepfellow.common.defaults import WORKSPACE_APP_SERVICE
from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.common.system import run
from deepfellow.workspace.utils.options import directory_option
from deepfellow.workspace.utils.validation import check_workspace_directory

app = typer.Typer()


@app.command()
def logs(
    directory: Path = directory_option("DeepFellow Workspace directory.", exists=True),
    follow: bool = typer.Option(False, "-f", "--follow", help="Follow log output"),
    tail: int | None = typer.Option(20, "-n", "--tail", help="Number of lines to show from the end of the logs"),
) -> None:
    """Show DeepFellow Workspace logs."""
    check_workspace_directory(directory)
    assert_docker()
    echo.info("Showing DeepFellow Workspace logs")

    cmd = ["docker", "compose", "logs", WORKSPACE_APP_SERVICE]
    if follow:
        cmd.append("-f")
    if tail is not None:
        cmd.extend(["--tail", str(tail)])

    run(cmd, cwd=directory)
