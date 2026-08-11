# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server env info command."""

from pathlib import Path

import typer

from deepfellow.common.defaults import DF_SERVER_STORAGE_DIRECTORY
from deepfellow.common.echo import echo
from deepfellow.common.env import EnvMetadata, get_envs_list, print_env_info
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


ENV_METADATA: dict[str, EnvMetadata] = {
    "DF_SERVER_PORT": EnvMetadata(description="Port exposed by the DeepFellow Server."),
    "DF_SERVER_URL": EnvMetadata(description="Public HTTP URL of the DeepFellow Server."),
    "DF_SERVER_IMAGE": EnvMetadata(description="Docker image used to run DeepFellow Server."),
    "DF_INFRA_DOCKER_SUBNET": EnvMetadata(
        description="Docker network/subnet shared with infrastructure services.",
    ),
    "DF_METRICS_USERNAME": EnvMetadata(
        description="Username used for metrics/authenticated monitoring access.",
    ),
    "DF_METRICS_PASSWORD": EnvMetadata(
        description="Password used for metrics/authenticated monitoring access.",
        sensitive=True,
    ),
    "DF_MONGO_URL": EnvMetadata(description="MongoDB connection host and port."),
    "DF_MONGO_PORT": EnvMetadata(description="Host port the local MongoDB instance is published on."),
    "DF_MONGO_USER": EnvMetadata(description="MongoDB username."),
    "DF_MONGO_PASSWORD": EnvMetadata(description="MongoDB password.", sensitive=True),
    "DF_MONGO_DB": EnvMetadata(description="MongoDB database name used by the server."),
    "DF_LOG_LEVEL": EnvMetadata(description="Log level of the DeepFellow Server (e.g. INFO, DEBUG)."),
    "DF_PLUGINS_SETUP": EnvMetadata(
        description="JSON object with plugin configuration (e.g. df_anonymize_models, df_abuse_model).",
    ),
    "DF_INFRA__URL": EnvMetadata(
        description="HTTP URL of the connected DeepFellow Infra instance.",
    ),
    "DF_INFRA__API_KEY": EnvMetadata(
        description="API key used to authenticate with DeepFellow Infra.",
        sensitive=True,
    ),
    "DF_VECTOR_DATABASE__PROVIDER__ACTIVE": EnvMetadata(
        description="Enable or disable vector database integration.",
    ),
    "DF_VECTOR_DATABASE__PROVIDER__TYPE": EnvMetadata(
        description="Type of vector database provider.",
    ),
    "DF_VECTOR_DATABASE__PROVIDER__URL": EnvMetadata(
        description="URL of the vector database service.",
    ),
    "DF_VECTOR_DATABASE__PROVIDER__USER": EnvMetadata(
        description="Username used for vector database authentication.",
    ),
    "DF_VECTOR_DATABASE__PROVIDER__PASSWORD": EnvMetadata(
        description="Password used for vector database authentication.",
        sensitive=True,
    ),
    "DF_VECTOR_DATABASE__EMBEDDING__ACTIVE": EnvMetadata(
        description="Enable or disable embeddings support.",
    ),
    "DF_VECTOR_DATABASE__EMBEDDING__ENDPOINT": EnvMetadata(
        description="Embedding provider endpoint identifier.",
    ),
    "DF_VECTOR_DATABASE__EMBEDDING__MODEL": EnvMetadata(
        description="Embedding model name used for vector generation.",
    ),
    "DF_VECTOR_DATABASE__EMBEDDING__SIZE": EnvMetadata(
        description="Embedding vector size/dimensions.",
    ),
    "DF_GRAPHITI__ENABLED": EnvMetadata(
        description="Enable or disable the Knowledge Graph (Neo4j) integration.",
    ),
    "DF_GRAPHITI__NEO4J_URI": EnvMetadata(
        description="Bolt connection URI for the Neo4j instance.",
    ),
    "DF_GRAPHITI__NEO4J_USER": EnvMetadata(
        description="Neo4j username.",
    ),
    "DF_GRAPHITI__NEO4J_PASSWORD": EnvMetadata(
        description="Neo4j password.",
        sensitive=True,
    ),
}


def _config_json_exists() -> bool:
    """Best-effort check for whether config.json has already been seeded on this server install.

    Existence alone doesn't mean any of the values below are stale — only that the Server's
    runtime config has diverged from `.env` for at least the fields that migrated into config.json.
    Unlike infra's storage dir, the server's storage directory isn't configurable per-install, so
    no `.env` lookup is needed.
    """
    return (DF_SERVER_STORAGE_DIRECTORY / "config.json").is_file()


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
    check_server_directory(directory)

    env_file = directory / ".env"
    envs = get_envs_list(env_file)
    env_values = dict(e.split("=", 1) for e in envs)

    if _config_json_exists():
        echo.warning(
            "config.json exists on this install — some of these values may be stale if they were migrated to "
            "dynamic configuration. Run `deepfellow server info` for the Server's current runtime configuration."
        )

    print_env_info(
        "Information about DeepFellow Server:", ENV_METADATA, env_values, show_secret=secret, doc=doc, show_prefix=True
    )
