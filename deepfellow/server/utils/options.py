# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Options for server."""

from pathlib import Path
from typing import Any

import typer

from deepfellow.common.defaults import DF_SERVER_DIRECTORY
from deepfellow.common.env import env_get, env_set
from deepfellow.common.state import state


def get_default_server_directory() -> Path:
    """Return default server directory."""
    config_file = state.cli_config_file

    default_dir = env_get(config_file, "DF_DEFAULT_SERVER_DIR", should_raise=False)

    if not default_dir:
        return DF_SERVER_DIRECTORY

    return Path(default_dir)


def set_default_server_directory(directory: str | Path, force: bool = False) -> None:
    """Sets default server directory."""
    config_file = state.cli_config_file

    if force:
        env_set(config_file, "DF_DEFAULT_SERVER_DIR", str(directory))
    else:
        current_default_server_directory = env_get(config_file, "DF_DEFAULT_SERVER_DIR", should_raise=False)
        if not current_default_server_directory:
            env_set(config_file, "DF_DEFAULT_SERVER_DIR", str(directory))


def default_directory_callback(dir: str | None) -> Path:
    """Return default server directory if str is None."""
    out_dir = DF_SERVER_DIRECTORY
    if dir is None:
        config_file = state.cli_config_file
        default_dir = env_get(config_file, "DF_DEFAULT_SERVER_DIR", should_raise=False)
        if default_dir:
            out_dir = Path(default_dir)

    else:
        out_dir = Path(dir)

    return out_dir.resolve()


def directory_option(
    help: str = "Directory of the DeepFellow Server installation.", exists: bool = False, **kwargs: Any
) -> Path:
    """Directory option for server commands."""
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
        None,
        "--directory",
        "--dir",
        envvar="DF_SERVER_DIRECTORY",
        help=help,
        callback=default_directory_callback,
        **kwargs,
    )
