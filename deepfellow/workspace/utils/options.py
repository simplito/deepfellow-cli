# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Options for workspace."""

from pathlib import Path
from typing import Any

import typer

from deepfellow.common.defaults import DF_WORKSPACE_DIRECTORY


def directory_option(help: str = "Directory of the DeepFellow Workspace installation.", **kwargs: Any) -> Path:
    """typer.Option wrapper for the directory option in workspace commands.

    Args:
        help: Help message to display in --help.
        **kwargs: Passed to typer.Option.

    Returns:
        The directory option.
    """
    return typer.Option(
        DF_WORKSPACE_DIRECTORY,
        "--directory",
        "--dir",
        envvar="DF_WORKSPACE_DIRECTORY",
        help=help,
        **kwargs,
    )
