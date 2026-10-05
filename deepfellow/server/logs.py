# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""DeepFellow server logs command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.common.system import run
from deepfellow.server.utils.docker import assert_nightshift_installed
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def logs(
    directory: Path = directory_option("Target directory for the server installation.", exists=True),
    follow: bool = typer.Option(False, "-f", "--follow", help="Follow log output"),
    tail: int | None = typer.Option(20, "-n", "--tail", help="Number of lines to show from the end of the logs"),
    nightshift: bool = typer.Option(False, help="Show the Nightshift worker's logs instead of the server's."),
) -> None:
    """Show DeepFellow Server logs."""
    assert_docker()
    if nightshift:
        assert_nightshift_installed(directory)
    service = "nightshift" if nightshift else "server"
    echo.info(f"Showing DeepFellow {'Nightshift worker' if nightshift else 'Server'} logs")

    cmd = ["docker", "compose", "logs", service]

    if follow:
        cmd.append("-f")

    if tail is not None:
        cmd.extend(["--tail", str(tail)])

    run(cmd, cwd=directory)
