# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""server nightshift status typer command."""

from pathlib import Path

import typer

from deepfellow.common.install import assert_docker
from deepfellow.server.utils.docker import print_nightshift_status
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


@app.command()
def status(
    directory: Path = directory_option(exists=True),
) -> None:
    """Show the Nightshift worker's configured mode/schedule and live container state."""
    check_server_directory(directory)
    assert_docker()

    print_nightshift_status(directory)
