# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""DeepFellow otel logs command."""

from pathlib import Path

import typer

from deepfellow.common.docker import is_service_running
from deepfellow.common.echo import echo
from deepfellow.common.system import run
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def logs(
    directory: Path = directory_option("Directory of the DeepFellow Server installation.", exists=True),
    follow: bool = typer.Option(False, "-f", "--follow", help="Follow log output"),
    tail: int = typer.Option(20, "-n", "--tail", help="Number of lines to show from the end of the logs"),
) -> None:
    """Show local OpenTelemetry collector logs."""
    if not (directory / "otel-collector-config.yaml").exists():
        echo.error("No local OpenTelemetry collector found. Install one with `deepfellow server install --otel-local`.")
        raise typer.Exit(1)

    if not is_service_running("otel-collector", directory):
        echo.error("The local OpenTelemetry collector is not running. Start it with `deepfellow server start`.")
        raise typer.Exit(1)

    echo.info("Showing local OpenTelemetry collector logs")

    cmd = ["docker", "compose", "logs", "otel-collector"]
    if follow:
        cmd.append("-f")
    if tail is not None:
        cmd.extend(["--tail", str(tail)])

    run(cmd, cwd=directory)
