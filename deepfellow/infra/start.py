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

from deepfellow.common.config import read_env_file_to_dict
from deepfellow.common.echo import echo
from deepfellow.infra.utils.docker import start_infra
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def start(
    directory: Path = directory_option(exists=True),
) -> None:
    """Start DeepFellow Infra."""
    env_file = directory / ".env"
    original_env_content = read_env_file_to_dict(env_file)
    echo.info("Starting DeepFellow Infra")
    start_infra(directory)
    echo.info(f"DeepFellow Infra started on http://localhost:{original_env_content['df_infra_port']}")
