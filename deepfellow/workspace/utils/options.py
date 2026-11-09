# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Options for workspace."""

from pathlib import Path
from typing import Any

import typer

from deepfellow.common.defaults import DF_WORKSPACE_DIRECTORY


def directory_option(
    help: str = "Directory of the DeepFellow Workspace installation.", exists: bool = False, **kwargs: Any
) -> Path:
    """typer.Option wrapper for the directory option in workspace commands.

    Args:
        help: Help message to display in --help.
        exists: Require an existing, readable and writable directory.
        **kwargs: Passed to typer.Option.

    Returns:
        The directory option.
    """
    if exists:
        kwargs |= {
            "exists": True,
            "file_okay": False,
            "dir_okay": True,
            "readable": True,
            "writable": True,
            "resolve_path": True,
        }

    return typer.Option(
        DF_WORKSPACE_DIRECTORY,
        "--directory",
        "--dir",
        envvar="DF_WORKSPACE_DIRECTORY",
        help=help,
        **kwargs,
    )
