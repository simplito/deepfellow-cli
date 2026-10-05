# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""server nightshift stop typer command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.server.utils.docker import assert_nightshift_installed, stop_nightshift
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


@app.command()
def stop(
    directory: Path = directory_option("Target directory for the server installation.", exists=True),
) -> None:
    """Stop the Nightshift worker container.

    In shift mode, the scheduled timer will start it again at its next configured hour regardless
    of this manual stop - use `server nightshift mode always` to disable the schedule entirely.
    """
    check_server_directory(directory)
    assert_docker()
    assert_nightshift_installed(directory)
    echo.info("Stopping DeepFellow Nightshift worker")
    stop_nightshift(directory)
    echo.success("DeepFellow Nightshift worker stopped.")
