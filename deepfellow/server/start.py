# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Start server typer command."""

from pathlib import Path

import typer

from deepfellow.common.config import read_env_file_to_dict
from deepfellow.common.docker import local_url
from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.server.utils.docker import start_server
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


@app.command()
def start(
    directory: Path = directory_option("Target directory for the server installation.", exists=True),
) -> None:
    """Start DeepFellow Server."""
    check_server_directory(directory)
    assert_docker()
    env_file = directory / ".env"
    original_env_content = read_env_file_to_dict(env_file)
    echo.info("Starting DeepFellow Server")
    start_server(directory)
    server_url = local_url(
        str(original_env_content["df_server_port"]), str(original_env_content.get("df_server_bind_address", ""))
    )
    echo.info(f"DeepFellow Server started on {server_url}")
