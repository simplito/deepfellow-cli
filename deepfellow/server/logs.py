# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""DeepFellow server logs command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.system import run
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def logs(
    directory: Path = directory_option("Target directory for the server installation.", exists=True),
    follow: bool = typer.Option(False, "-f", "--follow", help="Follow log output"),
    tail: int = typer.Option(20, "-n", "--tail", help="Number of lines to show from the end of the logs"),
) -> None:
    """Show DeepFellow Server logs."""
    echo.info("Showing DeepFellow Server logs")

    cmd = ["docker", "compose", "logs", "server"]

    if follow:
        cmd.append("-f")

    if tail is not None:
        cmd.extend(["--tail", str(tail)])

    run(cmd, cwd=directory)
