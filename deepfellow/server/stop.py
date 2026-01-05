# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Start server typer command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.system import run
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def stop(
    directory: Path = directory_option("Target directory for the server installation.", exists=True),
) -> None:
    """Stop DeepFellow Server."""
    echo.debug("Stopping DeepFellow Server")
    run(["docker", "compose", "down"], cwd=directory)
    echo.success("DeepFellow Server is down")
