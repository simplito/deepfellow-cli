# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Uninstall workspace typer command."""

from pathlib import Path

import typer

from deepfellow.common.defaults import DOCKER_COMPOSE_CONFIG_FILENAME
from deepfellow.common.docker import load_compose_file, resolve_compose_volume_name
from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.common.system import run
from deepfellow.workspace.utils.install import MONGO_VOLUME
from deepfellow.workspace.utils.options import directory_option

app = typer.Typer()


@app.command()
def uninstall(directory: Path = directory_option("DeepFellow Workspace directory.")) -> None:
    """Remove the DeepFellow Workspace containers; data, compose.yaml and .env are kept."""
    if not (directory / DOCKER_COMPOSE_CONFIG_FILENAME).is_file():
        echo.info(f"DeepFellow Workspace is already uninstalled (no {DOCKER_COMPOSE_CONFIG_FILENAME} in {directory}).")
        return

    assert_docker()
    echo.info("Turning off DeepFellow Workspace.")
    # `-v` drops the anonymous volumes of the images (Redis, Mongo config); the named Mongo data volume stays.
    run(["docker", "compose", "rm", "-s", "-f", "-v"], directory, quiet=True)
    run(["docker", "compose", "down", "--remove-orphans"], directory, quiet=True)
    kept = f"{directory / '.env'} and {directory / DOCKER_COMPOSE_CONFIG_FILENAME}"
    if MONGO_VOLUME in load_compose_file(directory / DOCKER_COMPOSE_CONFIG_FILENAME).get("volumes", {}):
        volume = resolve_compose_volume_name(directory, MONGO_VOLUME) or MONGO_VOLUME
        kept = f"its Mongo data (Docker volume {volume}), {kept}"
    echo.success(f"DeepFellow Workspace uninstalled. Kept: {kept}.")
