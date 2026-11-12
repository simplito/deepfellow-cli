# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Prune workspace typer command."""

from pathlib import Path

import typer

from deepfellow.common.defaults import DOCKER_COMPOSE_CONFIG_FILENAME
from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.common.system import rmtree, run
from deepfellow.workspace.utils.install import read_existing_env
from deepfellow.workspace.utils.options import directory_option
from deepfellow.workspace.utils.webhook import remove_webhook

app = typer.Typer()


@app.command()
def prune(directory: Path = directory_option("DeepFellow Workspace directory.")) -> None:
    """Remove DeepFellow Workspace: containers, Mongo and Redis volumes, files with secrets and the Server webhook."""
    if not directory.is_dir():
        echo.info(f"DeepFellow Workspace is already pruned (no {directory}).")
        return

    env = read_existing_env(directory)

    if (directory / DOCKER_COMPOSE_CONFIG_FILENAME).is_file():
        assert_docker()
        echo.info("Removing DeepFellow Workspace containers and volumes.")
        run(["docker", "compose", "down", "-v", "--remove-orphans"], directory, quiet=True)

    remove_webhook(env)

    echo.info("Removing DeepFellow Workspace files.")
    rmtree(directory)
    echo.success("DeepFellow Workspace pruned.")
