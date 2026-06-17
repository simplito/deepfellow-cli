# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Restart server typer command."""

from pathlib import Path

import typer

from deepfellow.common.config import read_env_file_to_dict
from deepfellow.common.echo import echo
from deepfellow.server.utils.docker import start_server, stop_server
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


@app.command()
def restart(
    directory: Path = directory_option("Target directory for the server installation.", exists=True),
) -> None:
    """Restart DeepFellow Server."""
    check_server_directory(directory)
    env_file = directory / ".env"
    original_env_content = read_env_file_to_dict(env_file)
    echo.info("Restarting DeepFellow Server")
    stop_server(directory)
    start_server(directory)
    echo.info(f"DeepFellow Server started on http://localhost:{original_env_content['df_server_port']}")
