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

from deepfellow.common.defaults import DF_INFRA_DIRECTORY


def directory_option(help: str = "Directory of the DeepFellow Infra installation.", **kwargs: Any) -> Path:
    """Directory option fot infra commands."""
    return typer.Option(
        DF_INFRA_DIRECTORY,
        "--directory",
        "--dir",
        envvar="DF_INFRA_DIRECTORY",
        help=help,
        **kwargs,
    )
