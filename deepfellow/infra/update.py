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

from deepfellow.common.config import (
    read_env_file_to_dict,
)
from deepfellow.common.defaults import DF_INFRA_IMAGE, DF_INFRA_IMAGE_HUB
from deepfellow.common.docker import load_compose_file, save_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.system import run
from deepfellow.infra.utils.docker import start_infra, stop_infra
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def update(
    directory: Path = directory_option(exists=True),
    image: str = typer.Option(DF_INFRA_IMAGE, envvar="DF_INFRA_IMAGE", help="DeepFellow Infra docker image."),
    local_image: bool = typer.Option(False, help="Use locally build DeepFellow Infra docker image."),
    tag: str | None = typer.Option(None, help="Deepfellow Infra docker image tag (e.g. 0.15.0)"),
) -> None:
    """Update DeepFellow Infra."""
    # Validate mutual exclusive image and tag
    if tag and image != DF_INFRA_IMAGE:
        raise typer.BadParameter("Only one if the `--tag` or `--image` options can be provided.")

    # Prepare the starting point for .env
    env_file = directory / ".env"
    infra_values = read_env_file_to_dict(env_file)

    # Prepare the docker compose data
    compose_file = directory / "docker-compose.yml"
    compose = load_compose_file(compose_file=compose_file)
    infra_service = compose["services"]["infra"]

    update_compose = False
    if local_image:
        if "pull_policy" not in infra_service:
            infra_service["pull_policy"] = "never"
            update_compose = True
    else:
        if "pull_policy" in infra_service:
            del infra_service["pull_policy"]
            update_compose = True

    if update_compose:
        save_compose_file(
            compose,
            directory / "docker-compose.yml",
        )

    if tag:
        image = f"{DF_INFRA_IMAGE_HUB}:{tag}"

    if infra_values["df_infra_image"] != image:
        env_set(env_file, "INFRA_IMAGE", image, quiet=False, docker_note=False)

    run(["docker", "compose", "pull", "infra"], cwd=directory)
    echo.success("Deepfellow Infra updated.")
    if echo.confirm("Do you want to restart?", default=True):
        stop_infra(directory)
        start_infra(directory)
