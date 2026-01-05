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
from deepfellow.server.utils.docker import start_server
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def start(
    directory: Path = directory_option("Target directory for the server installation.", exists=True),
) -> None:
    """Start DeepFellow Server."""
    echo.info("Starting DeepFellow Server")
    start_server(directory)
    echo.info("DeepFellow Server started.")
