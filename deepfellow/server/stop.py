# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Start server typer command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.common.system import run
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


@app.command()
def stop(
    directory: Path = directory_option("Target directory for the server installation.", exists=True),
) -> None:
    """Stop DeepFellow Server."""
    check_server_directory(directory)
    assert_docker()
    echo.debug("Stopping DeepFellow Server")
    run(["docker", "compose", "down"], cwd=directory)
    echo.success("DeepFellow Server is down")
