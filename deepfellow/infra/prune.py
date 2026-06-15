# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Prune infra command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.common.system import rmtree, run
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.validation import check_infra_directory

app = typer.Typer()


@app.command()
def prune(
    directory: Path = directory_option("DeepFellow Infra directory."),
) -> None:
    """Remove all DeepFellow Infra containers, volumes, and files."""
    echo.info("Pruning DeepFellow Infra.")
    check_infra_directory(directory)
    assert_docker()

    echo.info("Removing DeepFellow Infra containers and volumes.")
    run(["docker", "compose", "down", "-v"], directory, quiet=True)

    echo.info("Removing DeepFellow Infra files.")
    rmtree(directory)

    echo.success("DeepFellow Infra pruned.")
