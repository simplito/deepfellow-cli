# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Uninstall infra typer command."""

import json
from pathlib import Path

import typer

from deepfellow.common.config import read_env_file
from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.common.system import rmtree, run
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.validation import check_infra_directory

app = typer.Typer()

_ALREADY_UNINSTALLED_MESSAGE = "DeepFellow Infra is already uninstalled."
_ALREADY_UNINSTALLED_IMAGES_MESSAGE = (
    "DeepFellow Infra is already uninstalled - its Docker images can no longer be found. "
    "List and remove them manually - `docker images`, `docker image rm <image>`."
)


@app.command()
def uninstall(
    directory: Path = directory_option("DeepFellow Infra directory."),
    remove_images: bool | None = typer.Option(
        None,
        "--remove-images/--no-remove-images",
        help="Also remove Docker images used by DeepFellow Infra. If not given, asks interactively.",
    ),
) -> None:
    """Uninstall Deepfellow Infra."""
    echo.info("Uninstalling DeepFellow Infra.")
    missing_message = _ALREADY_UNINSTALLED_IMAGES_MESSAGE if remove_images else _ALREADY_UNINSTALLED_MESSAGE
    check_infra_directory(directory, missing_message=missing_message)
    assert_docker()

    images_output = run(
        ["docker", "compose", "images", "--format", "json"], cwd=directory, capture_output=True, check=False
    )
    parsed_images = json.loads(images_output) if images_output else None
    images = {f"{image['Repository']}:{image['Tag']}" for image in parsed_images} if parsed_images else set()

    env_file = directory / ".env"
    if env_file.is_file():
        df_infra_image = read_env_file(env_file).get("DF_INFRA_IMAGE")
        if df_infra_image:
            images.add(df_infra_image)

    echo.info("Turning off DeepFellow Infra.")
    run(["docker", "compose", "rm", "-s", "-f"], directory, quiet=True)

    flag_remove_images = remove_images if remove_images is not None else echo.confirm("Also remove Docker images?")
    if flag_remove_images:
        echo.info("Removing DeepFellow Infra Docker images.")
        for image in images:
            run(["docker", "image", "rm", image], quiet=True, check=False)
    else:
        echo.info("Docker images were not removed.")

    echo.info("Removing DeepFellow Infra files.")
    rmtree(directory)

    echo.success("DeepFellow Infra uninstalled.")
