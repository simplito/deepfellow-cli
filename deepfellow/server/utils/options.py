"""Options for infra."""

from pathlib import Path
from typing import Any

import typer

from deepfellow.common.defaults import DF_SERVER_DIRECTORY


def directory_option(help: str, **kwargs: Any) -> Path:
    """Directory option fot server commands."""
    return typer.Option(
        DF_SERVER_DIRECTORY,
        "--directory",
        "--dir",
        envvar="DF_SERVER_DIRECTORY",
        help=help,
        **kwargs,
    )
