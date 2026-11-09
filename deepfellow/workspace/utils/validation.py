# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Validation for workspace commands."""

from pathlib import Path

import typer

from deepfellow.common.defaults import DOCKER_COMPOSE_CONFIG_FILENAME
from deepfellow.common.echo import echo
from deepfellow.common.system import check_service_directory


def check_workspace_directory(directory: Path) -> None:
    """Exit when `directory` does not hold a DeepFellow Workspace installation.

    Args:
        directory: Workspace install directory.

    Raises:
        typer.Exit: When the directory or its compose file is missing.
    """
    message = f"No DeepFellow Workspace installation found in {directory}. Run 'workspace install' first."
    check_service_directory(directory, "Workspace", message)
    if not (directory / DOCKER_COMPOSE_CONFIG_FILENAME).is_file():
        echo.error(message)
        raise typer.Exit(1)
