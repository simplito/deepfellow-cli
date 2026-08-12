# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install server typer command."""

from pathlib import Path

import typer

from deepfellow.common.defaults import (
    DEFAULT_VECTOR_DATABASE,
    DEFAULT_VECTOR_DATABASE_TYPE,
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_URL,
    DF_MONGO_DB,
    DF_MONGO_PORT,
    DF_MONGO_URL,
    DF_NEO4J_URI,
    DF_SERVER_IMAGE,
    DF_SERVER_PORT,
    MILVUS_DATABASE,
    VectorDBTypeChoice,
)
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import InstallError, reraise_if_debug
from deepfellow.common.validation import validate_email, validate_password, validate_url
from deepfellow.server.utils.install import install as install_util
from deepfellow.server.utils.install import mergeable_field_names
from deepfellow.server.utils.options import directory_option, set_default_server_directory
from deepfellow.server.utils.templates import BUILTIN_TEMPLATES

app = typer.Typer()

_TEMPLATE_HELP = (
    "Built-in template name or path to a YAML template file.\n\n"
    f"Built-in templates: ({', '.join(sorted(BUILTIN_TEMPLATES))})"
)

# get_parameter_source() returns typer's own vendored ParameterSource enum (typer._click.core),
# not click.core's public one, so comparing by name is what actually works across typer versions
# without reaching into that private module.
_EXPLICIT_PARAMETER_SOURCE_NAMES = frozenset({"COMMANDLINE", "ENVIRONMENT"})


@app.command()
def install(
    ctx: typer.Context,
    directory: Path = directory_option(help="Target directory for the DeepFellow Server installation."),
    port: int = typer.Option(
        DF_SERVER_PORT, envvar="DF_SERVER_PORT", help="Port to use to serve the DeepFellow Server from."
    ),
    image: str = typer.Option(DF_SERVER_IMAGE, envvar="DF_SERVER_IMAGE", help="DeepFellow Server docker image."),
    local_image: bool = typer.Option(False, help="Use locally build DeepFellow Server docker image."),
    otel_url: str | None = typer.Option(
        None,
        envvar="DF_OTEL_EXPORTER_OTLP_ENDPOINT",
        help="Open Telemetry url (DF_OTEL_EXPORTER_OTLP_ENDPOINT).",
        callback=validate_url,
    ),
    otel_local: bool = typer.Option(
        False,
        "--otel-local",
        help="Install a local debug-only OpenTelemetry collector (mutually exclusive with --otel-url).",
    ),
    infra_url: str = typer.Option(
        DF_INFRA_URL, help="Deepfellow Infra url. Can be docker service url inside network or outside."
    ),
    infra_api_key: str = typer.Option(None, help="Deepfellow Infra api key"),
    docker_network: str = typer.Option(
        DF_INFRA_DOCKER_NETWORK, help="The Docker network name for container communication"
    ),
    mongodb_url: str = typer.Option(DF_MONGO_URL, help="The connection URL for the MongoDB instance"),
    mongodb_port: int = typer.Option(DF_MONGO_PORT, help="Host port to publish the local MongoDB on."),
    mongodb_database_name: str = typer.Option(DF_MONGO_DB, help="The name of the MongoDB database to use"),
    mongodb_username: str = typer.Option("", help="Username for MongoDB authentication"),
    mongodb_password: str = typer.Option("", help="Password for MongoDB authentication"),
    vectordb_active: bool = typer.Option(
        bool(DEFAULT_VECTOR_DATABASE["provider"]["active"]), help="Enable to use a vector database instance"
    ),
    vectordb_type: VectorDBTypeChoice = typer.Option(DEFAULT_VECTOR_DATABASE_TYPE, help="Type of Vector DB"),
    vectordb_url: str = typer.Option(
        DEFAULT_VECTOR_DATABASE["provider"]["url"], help="The connection URL for the remote Vector DB provider"
    ),
    vectordb_database_name: str = typer.Option(
        MILVUS_DATABASE["provider"]["db"], help="The collection or database name in the Vector DB"
    ),
    vectordb_username: str = typer.Option("", help="Username for Vector DB authentication"),
    vectordb_password: str = typer.Option("", help="Password for Vector DB authentication"),
    embedding_model: str = typer.Option(
        DEFAULT_VECTOR_DATABASE["embedding"]["model"], help="The model name used for generating vector embeddings"
    ),
    embedding_size: str = typer.Option(
        DEFAULT_VECTOR_DATABASE["embedding"]["size"], help="The dimensionality/size of the embedding vectors"
    ),
    embedding_sparse: bool = typer.Option(
        False, "--embedding-sparse", help="Use sparse embeddings (deepfellow-bge-m3, size 1024)."
    ),
    neo4j_active: bool = typer.Option(False, help="Enable the Knowledge Graph (Neo4j) instance."),
    neo4j_url: str = typer.Option(DF_NEO4J_URI, help="The connection URI for the Neo4j instance"),
    neo4j_username: str = typer.Option("", help="Username for Neo4j authentication"),
    neo4j_password: str = typer.Option("", help="Password for Neo4j authentication"),
    force_install: bool = typer.Option(False, help="Force install"),
    dev: bool = typer.Option(False, "--dev", help="Expose internal service ports to host for development."),
    template: str | None = typer.Option(None, help=_TEMPLATE_HELP),
    admin_name: str | None = typer.Option(None, "--admin-name", help="Admin user's name."),
    admin_email: str | None = typer.Option(None, "--admin-email", callback=validate_email, help="Admin user's email."),
    admin_password: str | None = typer.Option(
        None, "--admin-password", callback=validate_password, help="Admin user's password."
    ),
) -> None:
    """Install DeepFellow Server with docker."""
    # merged[key] != own_default can't tell an explicitly-passed flag from an unpassed one when the
    # two happen to be equal (e.g. an explicit `--port 8000` where 8000 is also port's own default) -
    # ctx.get_parameter_source() is the only way to know for sure, so it's computed here, once, from
    # the live Click invocation, and handed to install_util() instead of being re-derived from values.
    explicitly_provided = {
        key
        for key in mergeable_field_names()
        if (source := ctx.get_parameter_source(key)) is not None and source.name in _EXPLICIT_PARAMETER_SOURCE_NAMES
    }
    try:
        install_util(
            directory=directory,
            port=port,
            image=image,
            local_image=local_image,
            otel_url=otel_url,
            otel_local=otel_local,
            infra_url=infra_url,
            infra_api_key=infra_api_key,
            docker_network=docker_network,
            mongodb_url=mongodb_url,
            mongodb_port=mongodb_port,
            mongodb_database_name=mongodb_database_name,
            mongodb_username=mongodb_username,
            mongodb_password=mongodb_password,
            vectordb_active=vectordb_active,
            vectordb_type=vectordb_type,
            vectordb_url=vectordb_url,
            vectordb_database_name=vectordb_database_name,
            vectordb_username=vectordb_username,
            vectordb_password=vectordb_password,
            embedding_model=embedding_model,
            embedding_size=embedding_size,
            embedding_sparse=embedding_sparse,
            neo4j_active=neo4j_active,
            neo4j_url=neo4j_url,
            neo4j_username=neo4j_username,
            neo4j_password=neo4j_password,
            force_install=force_install,
            dev=dev,
            template=template,
            explicitly_provided=explicitly_provided,
            admin_name=admin_name,
            admin_email=admin_email,
            admin_password=admin_password,
        )
        set_default_server_directory(directory, force=False)
    except (InstallError, OSError) as exc:
        echo.error(str(exc))
        reraise_if_debug(exc)
