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


@app.command()
def uninstall(
    directory: Path = directory_option("DeepFellow Infra directory."),
    remove_images: bool = typer.Option(False, help="Also remove Docker images used by DeepFellow Infra."),
) -> None:
    """Uninstall Deepfellow Infra."""
    echo.info("Uninstalling DeepFellow Infra.")
    check_infra_directory(directory)
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

    echo.info("Removing DeepFellow Infra files.")
    rmtree(directory)

    if remove_images:
        echo.info("Removing DeepFellow Infra docker images.")
        for image in images:
            run(["docker", "image", "rm", image], quiet=True, check=False)
    else:
        echo.info("Docker images were not removed. Use --remove-images to also delete them.")

    echo.success("DeepFellow Infra uninstalled.")
