# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Restart infra typer command."""

from pathlib import Path

import typer

from deepfellow.common.config import read_env_file_to_dict
from deepfellow.common.echo import echo
from deepfellow.infra.utils.docker import start_infra, stop_infra
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.validation import check_infra_directory

app = typer.Typer()


@app.command()
def restart(
    directory: Path = directory_option(exists=True),
) -> None:
    """Restart DeepFellow Infra."""
    check_infra_directory(directory)
    env_file = directory / ".env"
    original_env_content = read_env_file_to_dict(env_file)
    echo.info("Restarting DeepFellow Infra")
    stop_infra(directory)
    start_infra(directory)
    echo.info(f"DeepFellow Infra started on http://localhost:{original_env_content['df_infra_port']}")
