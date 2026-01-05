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
from deepfellow.common.defaults import DF_SERVER_IMAGE, DF_SERVER_IMAGE_HUB
from deepfellow.common.docker import load_compose_file, save_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.system import run
from deepfellow.server.utils.docker import start_server, stop_server
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def update(
    directory: Path = directory_option(exists=True),
    image: str = typer.Option(DF_SERVER_IMAGE, envvar="DF_INFRA_IMAGE", help="DeepFellow Server docker image."),
    local_image: bool = typer.Option(False, help="Use locally build DeepFellow Server docker image."),
    tag: str | None = typer.Option(None, help="Deepfellow Server docker image tag (e.g. 0.15.0)"),
) -> None:
    """Update DeepFellow Server."""
    # Validate mutual exclusive image and tag
    if tag and image != DF_SERVER_IMAGE:
        raise typer.BadParameter("Only one if the `--tag` or `--image` options can be provided.")

    # Prepare the starting point for .env
    env_file = directory / ".env"
    values = read_env_file_to_dict(env_file)

    # Prepare the docker compose data
    compose_file = directory / "docker-compose.yml"
    compose = load_compose_file(compose_file=compose_file)
    service = compose["services"]["server"]

    update_compose = False
    if local_image:
        if "pull_policy" not in service:
            service["pull_policy"] = "never"
            update_compose = True
    else:
        if "pull_policy" in service:
            del service["pull_policy"]
            update_compose = True

    if update_compose:
        save_compose_file(
            compose,
            directory / "docker-compose.yml",
        )

    if tag:
        image = f"{DF_SERVER_IMAGE_HUB}:{tag}"

    if values["df_server_image"] != image:
        env_set(env_file, "SERVER_IMAGE", image, quiet=False, docker_note=False)

    run(["docker", "compose", "pull", "server"], cwd=directory)
    echo.success("DeepFellow Server updated.")
    if echo.confirm("Do you want to restart the server?", default=True):
        stop_server(directory)
        start_server(directory)
