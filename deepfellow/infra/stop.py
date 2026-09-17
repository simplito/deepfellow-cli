# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Start infra typer command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.common.system import run
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.validation import check_infra_directory

app = typer.Typer()


@app.command()
def stop(
    directory: Path = directory_option(exists=True),
) -> None:
    """Stop DeepFellow Infra."""
    check_infra_directory(directory)
    assert_docker()
    echo.debug("Stopping DeepFellow Infra")
    run(["docker", "compose", "down"], cwd=directory)
    echo.success("DeepFellow Infra is down")
