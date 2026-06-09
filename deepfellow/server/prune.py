# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Prune server command."""

import shutil
from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.common.system import run
from deepfellow.server.utils.options import directory_option, get_default_server_directory, set_default_server_directory
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


@app.command()
def prune(
    directory: Path = directory_option("DeepFellow Server directory."),
) -> None:
    """Remove all DeepFellow Server containers, volumes, and files."""
    echo.info("Pruning DeepFellow Server.")
    check_server_directory(directory)
    assert_docker()

    echo.info("Removing DeepFellow Server containers and volumes.")
    run(["docker", "compose", "down", "-v"], directory, quiet=True)

    echo.info("Removing DeepFellow Server files.")
    shutil.rmtree(directory)

    old_default_server_dir = get_default_server_directory()

    if old_default_server_dir.resolve() == directory.resolve():
        set_default_server_directory("", True)

    echo.success("DeepFellow Server pruned.")
