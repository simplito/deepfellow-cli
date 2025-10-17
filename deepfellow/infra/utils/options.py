"""Options for infra."""

from pathlib import Path
from typing import Any

import typer

from deepfellow.common.defaults import DF_INFRA_DIRECTORY


def directory_option(help: str, **kwargs: Any) -> Path:
    """Directory option fot infra commands."""
    return typer.Option(
        DF_INFRA_DIRECTORY,
        "--directory",
        "--dir",
        envvar="DF_INFRA_DIRECTORY",
        help=help,
        **kwargs,
    )
