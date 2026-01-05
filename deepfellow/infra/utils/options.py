# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
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

from deepfellow.common.defaults import DF_INFRA_DIRECTORY


def directory_option(
    help: str = "Directory of the DeepFellow Infra installation.", exists: bool = False, **kwargs: Any
) -> Path:
    """typer.Option wrapper for d option in infra commands.

    Arguments:
        help (str): help message to display in --help
        exists (bool): should we check if directory exists and is readable/writable
        kwargs (Any): kwargs to be passed to typer.Option

    Returns:
        Path of the infra directory
    """
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
        DF_INFRA_DIRECTORY,
        "--directory",
        "--dir",
        envvar="DF_INFRA_DIRECTORY",
        help=help,
        **kwargs,
    )
