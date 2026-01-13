# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra disconnect command."""

from pathlib import Path

import typer

from deepfellow.common.docker import is_service_running
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get, env_set
from deepfellow.common.system import run
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def disconnect(
    directory: Path = directory_option(exists=True),
) -> None:
    """Disconnect infra. This infra is child."""
    if not is_service_running("infra", cwd=directory):
        echo.error("DeepFellow Infra is not running")
        echo.info("Call `deepfellow infra start`")
        raise typer.Exit(1)

    env_file = directory / ".env"
    parent_infra_url = env_get(env_file, "DF_CONNECT_TO_MESH_URL")

    if parent_infra_url:
        if echo.confirm(f"Are you sure you want to disconnect from {parent_infra_url}", default=False):
            echo.info(f"Disconnecting from {parent_infra_url} ...")
            env_set(env_file, "DF_CONNECT_TO_MESH_URL", "")
            env_set(env_file, "DF_CONNECT_TO_MESH_KEY", "")

            echo.info("Restarting this instance DeepFellow Infra ...")
            run(["docker", "compose", "down"], cwd=directory, quiet=True)
            run(["docker", "compose", "up", "-d", "--remove-orphans"], cwd=directory, quiet=True)

            echo.success(f"DeepFellow Infra is disconnected from another Deepfellow Infra at {parent_infra_url}")
        else:
            echo.success("Operation ends with no changes.")
    else:
        echo.error("Already disconnected")
