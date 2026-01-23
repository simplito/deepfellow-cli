# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Uninstall infra typer command."""

import shutil
from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.common.system import run
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.validation import check_infra_directory

app = typer.Typer()


@app.command()
def uninstall(
    directory: Path = directory_option("DeepFellow Infra directory."),
) -> None:
    """Uninstall Deepfellow Infra."""
    echo.info("Uninstalling DeepFellow Infra.")
    check_infra_directory(directory)
    assert_docker()

    echo.info("Turn off DeepFellow Infra.")
    run(["docker", "compose", "rm", "-s", "-f"], directory, quiet=True)

    echo.info("Removing DeepFellow Infra files.")
    shutil.rmtree(directory)

    echo.success("DeepFellow Infra uninstalled.")
