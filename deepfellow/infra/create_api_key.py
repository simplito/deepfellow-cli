# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Create API Key typer command."""

import typer

from deepfellow.common.config import get_config_path
from deepfellow.common.echo import echo

app = typer.Typer()


@app.command()
def create_api_key() -> None:
    """Create API Key DeepFellow Infra."""
    config = get_config_path()
    typer.echo(f"DeepFellow Infra create-api-key using config: {config}")
    echo.info("Creating API Key for DeepFellow Infra")
