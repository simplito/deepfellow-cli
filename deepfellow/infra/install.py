# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install infra typer command."""

from pathlib import Path

import typer

from deepfellow.common.defaults import (
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_IMAGE,
    DF_INFRA_NAME,
    DF_INFRA_PORT,
    DF_INFRA_STORAGE_DIR,
    DF_INFRA_URL,
)
from deepfellow.infra.utils.install import install as install_util
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def install(
    directory: Path = directory_option("Target directory for the DeepFellow Infra installation."),
    port: int = typer.Option(
        DF_INFRA_PORT, envvar="DF_INFRA_PORT", help="Published port to serve the DeepFellow Infra from."
    ),
    image: str = typer.Option(DF_INFRA_IMAGE, envvar="DF_INFRA_IMAGE", help="DeepFellow Infra docker image."),
    local_image: bool = typer.Option(False, help="Use locally build DeepFellow Infra docker image."),
    docker_config: Path | None = typer.Option(None, envvar="DF_INFRA_DOCKER_CONFIG", help="Path to the docker config."),
    storage: Path = typer.Option(
        DF_INFRA_STORAGE_DIR, envvar="DF_INFRA_STORAGE_DIR", help="Storage for the DeepFellow Infra services."
    ),
    hugging_face_token: str | None = typer.Option(None, envvar="DF_HUGGING_FACE_TOKEN", help="Hugging Face Token"),
    civitai_token: str | None = typer.Option(None, envvar="DF_CIVITAI_TOKEN", help="Civitai Token"),
    infra_name: str = typer.Option(DF_INFRA_NAME, help="Deepfellow Infra name"),
    infra_url: str = typer.Option(DF_INFRA_URL, envvar="DF_INFRA_URL", help="Deepfellow Infra URL"),
    docker_network: str = typer.Option(
        DF_INFRA_DOCKER_NETWORK, envvar="DF_INFRA_DOCKER_NETWORK", help="Docker network"
    ),
    force_install: bool = typer.Option(False, help="Force install"),
    allow_rootful: bool = typer.Option(False, help="Allow rootful Docker without asking user for permission"),
) -> None:
    """Install infra with docker."""
    install_util(
        directory=directory,
        port=port,
        image=image,
        local_image=local_image,
        docker_config=docker_config,
        storage=storage,
        hugging_face_token=hugging_face_token,
        civitai_token=civitai_token,
        infra_name=infra_name,
        infra_url=infra_url,
        docker_network=docker_network,
        force_install=force_install,
        allow_rootful=allow_rootful,
    )
