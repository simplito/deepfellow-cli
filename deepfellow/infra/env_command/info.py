# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra env info command."""

from pathlib import Path

import typer

from deepfellow.common.defaults import DF_INFRA_STORAGE_DIR
from deepfellow.common.echo import echo
from deepfellow.common.env import EnvMetadata, get_envs_list, print_env_info
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.validation import check_infra_directory

app = typer.Typer()


ENV_METADATA: dict[str, EnvMetadata] = {
    "DF_NAME": EnvMetadata(description="Name of the infrastructure instance."),
    "DF_INFRA_URL": EnvMetadata(description="Base HTTP URL of the DeepFellow Infra service."),
    "DF_INFRA_MESH_URL": EnvMetadata(description="WebSocket URL used for mesh communication."),
    "DF_INFRA_PORT": EnvMetadata(description="Port exposed by the Infra service."),
    "DF_INFRA_IMAGE": EnvMetadata(description="Docker image used to run DeepFellow Infra."),
    "DF_MESH_KEY": EnvMetadata(
        description="Authentication key used for mesh communication.",
        sensitive=True,
    ),
    "DF_INFRA_API_KEY": EnvMetadata(
        description="API key used to access Infra endpoints.",
        sensitive=True,
    ),
    "DF_INFRA_ADMIN_API_KEY": EnvMetadata(
        description="Administrative API key with elevated privileges.",
        sensitive=True,
    ),
    "DF_CONNECT_TO_MESH_URL": EnvMetadata(description="Optional remote mesh URL to connect to."),
    "DF_CONNECT_TO_MESH_KEY": EnvMetadata(
        description="Authentication key for remote mesh connection.",
        sensitive=True,
    ),
    "DF_INFRA_DOCKER_SUBNET": EnvMetadata(
        description="Docker network/subnet name used by Infra containers.",
    ),
    "DF_INFRA_COMPOSE_PREFIX": EnvMetadata(
        description="Prefix used for generated Docker Compose resources.",
    ),
    "DF_INFRA_DOCKER_CONFIG": EnvMetadata(description="Path to Docker client configuration file."),
    "DF_INFRA_STORAGE_DIR": EnvMetadata(description="Directory used for Infra persistent storage."),
    "DF_METRICS_USERNAME": EnvMetadata(
        description="Username used for metrics/authenticated monitoring access.",
    ),
    "DF_METRICS_PASSWORD": EnvMetadata(
        description="Password used for metrics/authenticated monitoring access.",
        sensitive=True,
    ),
}


def _config_json_exists(env_values: dict[str, str]) -> bool:
    """Best-effort check for whether config.json has already been seeded on this infra install.

    Existence alone doesn't mean any of the values below are stale — only that Infra's runtime
    config has diverged from `.env` for at least the fields that migrated into config.json.
    """
    storage_dir = env_values.get("DF_INFRA_STORAGE_DIR") or str(DF_INFRA_STORAGE_DIR)
    return (Path(storage_dir) / "config.json").is_file()


@app.command()
def info(
    directory: Path = directory_option(),
    secret: bool = typer.Option(
        False,
        "--secret",
        help="Display sensitive values.",
    ),
    doc: bool = typer.Option(
        False,
        "--doc",
        help="Display environment variables documentation.",
    ),
) -> None:
    """Display environment variables from the local .env file."""
    check_infra_directory(directory)

    env_file = directory / ".env"
    envs = get_envs_list(env_file)

    env_values: dict[str, str] = dict(e.split("=", 1) for e in envs)

    if "DF_INFRA_URL" in env_values:
        env_values["DF_INFRA_MESH_URL"] = (
            env_values["DF_INFRA_URL"].replace("http://", "ws://").replace("https://", "wss://")
        )

    if _config_json_exists(env_values):
        echo.warning(
            "config.json exists on this install — some of these values may be stale if they were migrated to "
            "dynamic configuration. Run `deepfellow infra info` for Infra's current runtime configuration."
        )

    print_env_info(
        "Information about DeepFellow Infra:", ENV_METADATA, env_values, show_secret=secret, doc=doc, show_prefix=True
    )
