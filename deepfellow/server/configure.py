# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Configure server typer command."""

import typer

from deepfellow.common.config import get_config_path
from deepfellow.common.echo import echo

app = typer.Typer()


@app.command()
def configure() -> None:
    """Configure server."""
    config = get_config_path()
    typer.echo(f"Deepfellow Server configure using config: {config}")
    echo.info("Configuring Deepfellow Server")
    echo.info("Retrive info about access to DeepFellow Infra, database.")
