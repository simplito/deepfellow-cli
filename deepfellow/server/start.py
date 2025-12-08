# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Start server typer command."""

from pathlib import Path

import typer

from deepfellow.common.config import env_to_dict, read_env_file
from deepfellow.common.docker import ensure_network
from deepfellow.common.echo import echo
from deepfellow.common.system import run
from deepfellow.common.validation import validate_directory
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def start(
    directory: Path = directory_option(
        "Target directory for the server installation.",
        callback=validate_directory,
    ),
) -> None:
    """Start DeepFellow Server."""
    echo.info("Starting DeepFellow Server")
    env_file = directory / ".env"
    env_vars = read_env_file(env_file)
    env_content = env_to_dict(env_vars)
    docker_network = env_content.get("df_infra_docker_subnet", "")
    ensure_network(str(docker_network))
    run("docker compose up -d --remove-orphans", cwd=directory)
    echo.info("DeepFellow Server started.")
