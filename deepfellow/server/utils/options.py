# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Options for infra."""

from pathlib import Path
from typing import Any

import typer

from deepfellow.common.defaults import DF_SERVER_DIRECTORY


def directory_option(
    help: str = "Directory of the DeepFellow Server installation.", exists: bool = False, **kwargs: Any
) -> Path:
    """Directory option fot server commands."""
    if exists:
        kwargs |= {
            "exists": True,
            "file_okay": False,  # can't be a file
            "dir_okay": True,  # can be a directory
            "readable": True,
            "writable": True,
            "resolve_path": True,  # convert from symlinks to absolute path
        }

    return typer.Option(
        DF_SERVER_DIRECTORY,
        "--directory",
        "--dir",
        envvar="DF_SERVER_DIRECTORY",
        help=help,
        **kwargs,
    )
