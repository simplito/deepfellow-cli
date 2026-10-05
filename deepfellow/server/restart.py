# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Restart server typer command."""

from pathlib import Path

import typer

from deepfellow.common.config import read_env_file_to_dict
from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.server.utils.docker import reconcile_nightshift_running_state, start_server, stop_server
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


@app.command()
def restart(
    directory: Path = directory_option("Target directory for the server installation.", exists=True),
) -> None:
    """Restart DeepFellow Server."""
    check_server_directory(directory)
    assert_docker()
    env_file = directory / ".env"
    original_env_content = read_env_file_to_dict(env_file)
    echo.info("Restarting DeepFellow Server")
    stop_server(directory)
    start_server(directory)
    # stop_server()/start_server() are scoped to the "server" container - reconcile explicitly
    # here too, rather than relying on start_server()'s own --scale nightshift=0 side effect,
    # so the worker's schedule compliance is a documented, tested part of `restart`, not incidental.
    reconcile_nightshift_running_state(directory)
    echo.info(f"DeepFellow Server started on http://localhost:{original_env_content['df_server_port']}")
