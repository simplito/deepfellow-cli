# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install server typer command."""

from copy import deepcopy
from pathlib import Path
from typing import cast

import typer

from deepfellow.common.config import read_env_file_to_dict, save_env_file
from deepfellow.common.defaults import (
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_URL,
    DF_MONGO_DB,
    DF_MONGO_PASSWORD,
    DF_MONGO_URL,
    DF_MONGO_USER,
    DF_SERVER_IMAGE,
    DF_SERVER_PORT,
    DF_SERVER_STORAGE_DIRECTORY,
    DOCKER_COMPOSE_MONGO_DB,
    DOCKER_COMPOSE_SERVER,
    DOCKER_COMPOSE_VECTOR_DB,
    VECTOR_DATABASE,
)
from deepfellow.common.docker import (
    add_network_to_service,
    ensure_network,
    save_compose_file,
)
from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker, ensure_directory
from deepfellow.common.system import run
from deepfellow.common.validation import validate_url
from deepfellow.server.utils.configure import configure_infra, configure_mongo, configure_otel, configure_vector_db
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def install(  # noqa: C901
    directory: Path = directory_option("Target directory for the DeepFellow Server installation."),
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
    infra_url: str = typer.Option(
        DF_INFRA_URL, help="Deepfellow Infra url. Can be docker service url inside network or outside."
    ),
    infra_api_key: str = typer.Option("", help="Deepfellow Infra api key"),
    docker_network: str = typer.Option(
        DF_INFRA_DOCKER_NETWORK, help="The Docker network name for container communication"
    ),
    mongodb_url: str = typer.Option(DF_MONGO_URL, help="The connection URL for the MongoDB instance"),
    mongodb_database_name: str = typer.Option(DF_MONGO_DB, help="The name of the MongoDB database to use"),
    mongodb_username: str = typer.Option(DF_MONGO_USER, help="Username for MongoDB authentication"),
    mongodb_password: str = typer.Option(DF_MONGO_PASSWORD, help="Password for MongoDB authentication"),
    vectordb_local: int = typer.Option(
        VECTOR_DATABASE["provider"]["active"], help="Enable to use a local vector database instance"
    ),
    vectordb_url: str = typer.Option(
        VECTOR_DATABASE["provider"]["url"], help="The connection URL for the remote Vector DB provider"
    ),
    vectordb_type: str = typer.Option(VECTOR_DATABASE["provider"]["type"], help="Type of Vector DB"),
    vectordb_database_name: str = typer.Option(
        VECTOR_DATABASE["provider"]["db"], help="The collection or database name in the Vector DB"
    ),
    vectordb_username: str = typer.Option(
        VECTOR_DATABASE["provider"]["user"], help="Username for Vector DB authentication"
    ),
    vectordb_password: str = typer.Option(
        VECTOR_DATABASE["provider"]["password"], help="Password for Vector DB authentication"
    ),
    embedding_active: int = typer.Option(VECTOR_DATABASE["embedding"]["active"], help="Active embedding"),
    embedding_endpoint: str = typer.Option(
        VECTOR_DATABASE["embedding"]["endpoint"], help="The model endpoint used for generating vector embeddings"
    ),
    embedding_model: str = typer.Option(
        VECTOR_DATABASE["embedding"]["model"], help="The model name used for generating vector embeddings"
    ),
    embedding_size: str = typer.Option(
        VECTOR_DATABASE["embedding"]["size"], help="The dimensionality/size of the embedding vectors"
    ),
    force_install: bool = typer.Option(False, help="Force install"),
) -> None:
    """Install DeepFellow Server with docker."""
    echo.info("Installing DeepFellow Server.")

    assert_docker()

    ensure_directory(
        directory, error_message="Unable to create DeepFellow Server directory.", force_install=force_install
    )

    env_file = directory / ".env"
    original_env_content = read_env_file_to_dict(env_file)

    echo.info("DeepFellow Server requires a MongoDB to be installed.")
    if (
        mongodb_url != DF_MONGO_URL
        or mongodb_database_name != DF_MONGO_DB
        or mongodb_username != DF_MONGO_USER
        or mongodb_password != DF_MONGO_PASSWORD
    ):
        custom_mongo_db_server = True
    else:
        custom_mongo_db_server = echo.confirm("Do you have MongoDB installed for DeepFellow Server?", default=False)

    mongo_env = configure_mongo(
        custom_mongo_db_server,
        original_env_content,
        mongodb_url,
        mongodb_username,
        mongodb_password,
        mongodb_database_name,
    )

    echo.info("DeepFellow Server is communicating with DeepFellow Infra.")
    infra_env = configure_infra(infra_api_key, infra_url, original_env_content)

    # Find out which docker network to use
    docker_network = echo.prompt(
        "Provide a docker network name",
        from_args=docker_network,
        original_default=DF_INFRA_DOCKER_NETWORK,
        default=original_env_content.get("df_infra_docker_subnet", docker_network),
    )

    # Create the network if needed
    ensure_network(docker_network)

    echo.info("DeepFellow Server might use a vector DB. If not provided some features will not work.")
    if (
        vectordb_local != VECTOR_DATABASE["provider"]["active"]
        or vectordb_type != VECTOR_DATABASE["provider"]["type"]
        or vectordb_url != VECTOR_DATABASE["provider"]["url"]
        or vectordb_database_name != VECTOR_DATABASE["provider"]["db"]
        or vectordb_username != VECTOR_DATABASE["provider"]["user"]
        or vectordb_password != VECTOR_DATABASE["provider"]["password"]
        or embedding_active != VECTOR_DATABASE["embedding"]["active"]
        or embedding_endpoint != VECTOR_DATABASE["embedding"]["endpoint"]
        or embedding_model != VECTOR_DATABASE["embedding"]["model"]
        or embedding_size != VECTOR_DATABASE["embedding"]["size"]
    ):
        custom_vector_db_server = True
    else:
        custom_vector_db_server = echo.confirm("Do you have a vector DB ready?", default=False)

    vector_db_envs = configure_vector_db(
        custom_vector_db_server,
        infra_env["DF_INFRA__URL"],
        original_env_content,
        vectordb_local,
        vectordb_type,
        vectordb_url,
        vectordb_database_name,
        vectordb_username,
        vectordb_password,
        embedding_active,
        embedding_endpoint,
        embedding_model,
        embedding_size,
    )
    vector_db_active = vector_db_envs.get("DF_VECTOR_DATABASE__PROVIDER__ACTIVE") == "1"

    otel = configure_otel(directory, otel_url, original_env_content)

    save_env_file(
        env_file,
        {
            "DF_SERVER_PORT": port,
            "DF_SERVER_URL": f"http://localhost:{port}",
            "DF_SERVER_IMAGE": image,
            "DF_INFRA_DOCKER_SUBNET": docker_network,
            **mongo_env,
            **infra_env,
            **vector_db_envs,
            **otel.envs,
        },
    )

    volumes: dict[str, None] = {}
    services = {}
    depends_on = {}

    if not custom_vector_db_server and vector_db_active:
        services.update(DOCKER_COMPOSE_VECTOR_DB)
        volumes.update({"milvus": None, "etcd": None, "minio": None})
        depends_on.update({"milvus": {"condition": "service_healthy"}})

    if not custom_mongo_db_server:
        services.update(DOCKER_COMPOSE_MONGO_DB)
        volumes["mongo"] = None
        depends_on.update({"mongo": {"condition": "service_healthy"}})

    compose_server = deepcopy(DOCKER_COMPOSE_SERVER)
    environment = cast("list", compose_server["server"]["environment"])
    for api_endpoint_key in infra_env:
        environment.append(api_endpoint_key + "=${" + api_endpoint_key + "}")

    if otel.docker_compose:
        services.update(otel.docker_compose)
        depends_on["otel-collector"] = {"condition": "service_started"}

    if otel.envs.get("DF_OTEL_TRACING_ENABLED") == "true" and otel.envs.get("DF_OTEL_EXPORTER_OTLP_ENDPOINT"):
        environment.append("DF_OTEL_EXPORTER_OTLP_ENDPOINT=${DF_OTEL_EXPORTER_OTLP_ENDPOINT}")
        environment.append("DF_OTEL_TRACING_ENABLED=${DF_OTEL_TRACING_ENABLED}")

    if not vector_db_active:
        compose_server["server"]["environment"] = [
            env for env in environment if not env.startswith("DF_VECTOR_DATABASE__") or "ACTIVE" in env
        ]

    if depends_on:
        compose_server["server"]["depends_on"] = depends_on

    if local_image:
        compose_server["server"]["pull_policy"] = "never"

    services.update(compose_server)

    for _, service in services.items():
        add_network_to_service(service, docker_network)

    # Create directory for plugins
    plugins_directory = directory / "plugins"
    plugins_directory.mkdir(exist_ok=True)

    services["server"]["volumes"] = [
        f"{DF_SERVER_STORAGE_DIRECTORY}:/app/storage",
        f"{plugins_directory.as_posix()}:/app/plugins",
    ]

    save_compose_file(
        {"services": services, "volumes": volumes, "networks": {docker_network: {"external": True}}},
        directory / "docker-compose.yml",
    )
    run(["docker", "compose", "pull"], directory)
    echo.success("DeepFellow Server Installed.\nCall `deepfellow server start`.")
