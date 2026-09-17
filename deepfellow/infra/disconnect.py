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
from deepfellow.common.env import env_get
from deepfellow.common.install import assert_docker
from deepfellow.infra.utils.admin import infra_admin_request
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.validation import check_infra_directory

app = typer.Typer()


@app.command()
def disconnect(
    directory: Path = directory_option(exists=True),
) -> None:
    """Disconnect infra. This infra is child."""
    check_infra_directory(directory)
    assert_docker()

    if not is_service_running("infra", cwd=directory):
        echo.error("DeepFellow Infra is not running")
        echo.info("Call `deepfellow infra start`")
        raise typer.Exit(1)

    env_file = directory / ".env"
    infra_port = env_get(env_file, "DF_INFRA_PORT", should_raise=False)
    admin_api_key = env_get(env_file, "DF_INFRA_ADMIN_API_KEY", should_raise=False)

    if not infra_port or not admin_api_key:
        echo.error("Could not resolve DF_INFRA_PORT / DF_INFRA_ADMIN_API_KEY from the instance .env file.")
        raise typer.Exit(1)

    local_infra_url = f"http://localhost:{infra_port}"
    config = infra_admin_request("GET", f"{local_infra_url}/admin/config", local_infra_url, admin_api_key)
    parent_infra_url = next(
        (entry.get("value") for entry in config.get("entries", []) if entry.get("key") == "connect_to_mesh_url"), None
    )

    if parent_infra_url:
        if echo.confirm(f"Are you sure you want to disconnect from {parent_infra_url}", default=False):
            echo.info(f"Disconnecting from {parent_infra_url} ...")
            infra_admin_request(
                "PUT",
                f"{local_infra_url}/admin/config",
                local_infra_url,
                admin_api_key,
                json_body={"connect_to_mesh_url": "", "connect_to_mesh_key": ""},
            )

            echo.success(f"DeepFellow Infra is disconnected from another Deepfellow Infra at {parent_infra_url}")
        else:
            echo.success("Operation ends with no changes.")
    else:
        echo.error("Already disconnected")
