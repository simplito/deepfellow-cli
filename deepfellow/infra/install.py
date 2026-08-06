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
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import InstallError, reraise_if_debug
from deepfellow.infra.utils.install import install as install_util
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.templates import BUILTIN_TEMPLATES

app = typer.Typer()

_TEMPLATE_HELP = (
    "Built-in template name or path to a YAML template file.\n\n"
    f"Built-in templates: ({', '.join(sorted(BUILTIN_TEMPLATES))})"
)


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
    template: str | None = typer.Option(None, help=_TEMPLATE_HELP),
    force_install: bool = typer.Option(False, help="Force install"),
    allow_rootful: bool = typer.Option(False, help="Allow rootful Docker without asking user for permission"),
    allow_print_keys: bool | None = typer.Option(
        None,
        "--allow-print-keys/--no-allow-print-keys",
        help="Print API keys to the console. If not given, asks interactively (default: don't print).",
    ),
    keep_compose_prefix: bool | None = typer.Option(
        None,
        "--keep-compose-prefix/--no-keep-compose-prefix",
        help="Keep the previously configured compose prefix, if any. If not given, asks interactively (default: keep).",
    ),
    keep_storage: bool | None = typer.Option(
        None,
        "--keep-storage/--no-keep-storage",
        help="Keep the previously configured storage dir, if any. If not given, asks interactively (default: keep).",
    ),
    keep_metrics: bool | None = typer.Option(
        None,
        "--keep-metrics/--no-keep-metrics",
        help="Keep the previously configured metrics credentials, if any. "
        "If not given, asks interactively (default: keep).",
    ),
) -> None:
    """Install infra with docker."""
    try:
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
            template=template,
            force_install=force_install,
            allow_rootful=allow_rootful,
            allow_print_keys=allow_print_keys,
            keep_compose_prefix=keep_compose_prefix,
            keep_storage=keep_storage,
            keep_metrics=keep_metrics,
        )
    except InstallError as exc:
        echo.error(str(exc))
        reraise_if_debug(exc)
