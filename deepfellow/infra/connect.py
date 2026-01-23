# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra connect command."""

from pathlib import Path

import typer

from deepfellow.common.docker import is_service_running
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get, env_set
from deepfellow.common.system import run
from deepfellow.common.validation import validate_url
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.validation import check_infra_directory

app = typer.Typer()


@app.command()
def connect(
    directory: Path = directory_option(exists=True),
    parent_infra_url: str = typer.Argument(
        ..., help="Parent DeepFellow Infra address (DF_INFRA_MESH_URL).", callback=validate_url
    ),
    mesh_key: str = typer.Argument(..., help="DF_MESH_KEY of the Parent DeepFellow Infra."),
) -> None:
    """Connect two Infras together. This infra is child."""
    check_infra_directory(directory)

    if not is_service_running("infra", cwd=directory):
        echo.error("DeepFellow Infra is not running")
        echo.info("Call `deepfellow infra start`")
        raise typer.Exit(1)

    env_file = directory / ".env"
    original_parent_infra_url = env_get(env_file, "DF_CONNECT_TO_MESH_URL")

    if original_parent_infra_url:
        echo.info(f"Disconnecting from {original_parent_infra_url} ...")

    env_set(env_file, "DF_CONNECT_TO_MESH_URL", parent_infra_url)
    env_set(env_file, "DF_CONNECT_TO_MESH_KEY", mesh_key)

    echo.info("Restarting this instance DeepFellow Infra ...")
    run(["docker", "compose", "down"], cwd=directory, quiet=True)
    run(["docker", "compose", "up", "-d", "--remove-orphans"], cwd=directory, quiet=True)

    echo.success(f"DeepFellow Infra is connected to another Infra at {parent_infra_url}")
