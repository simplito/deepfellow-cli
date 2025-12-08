# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra env set command."""

from pathlib import Path

import typer

from deepfellow.common.env import env_set
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def set(
    directory: Path = directory_option(),
    env_name: str = typer.Argument(..., help="Name of the environment variable", callback=lambda x: x.upper()),
    env_value: str = typer.Argument("", help="Value of the environment variable"),
    df_prefix: bool = typer.Option(True, help="Add DF_ prefix if not provided?"),
) -> None:
    """Set environment configuration."""
    env_set(directory / ".env", env_name, env_value, df_prefix)
