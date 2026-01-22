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

from deepfellow.common.docker import print_docker_status
from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def status(
    directory: Path = directory_option(exists=True),
) -> None:
    """Show DeepFellow Infra status."""
    assert_docker()
    echo.debug("Showing DeepFellow Infra status")
    print_docker_status(directory, "infra")
