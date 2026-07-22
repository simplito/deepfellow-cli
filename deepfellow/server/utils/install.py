# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install server core logic."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import typer

from deepfellow.common.config import read_env_file_to_dict, save_env_file
from deepfellow.common.defaults import (
    DEFAULT_VECTOR_DATABASE,
    DEFAULT_VECTOR_DATABASE_TYPE,
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_URL,
    DF_MONGO_DB,
    DF_MONGO_PORT,
    DF_MONGO_URL,
    DF_SERVER_DIRECTORY,
    DF_SERVER_IMAGE,
    DF_SERVER_IMAGE_HUB,
    DF_SERVER_PORT,
    DF_SERVER_STORAGE_DIRECTORY,
    DOCKER_COMPOSE_CONFIG_FILENAME,
    DOCKER_COMPOSE_MILVUS,
    DOCKER_COMPOSE_MONGO_DB,
    DOCKER_COMPOSE_QDRANT,
    DOCKER_COMPOSE_SERVER,
    DOCKER_COMPOSE_SERVER_VECTOR_DB_ENVS,
    DOCKER_COMPOSE_SERVER_VECTOR_DB_MILVUS_ENVS,
    MILVUS_DATABASE,
    VectorDBTypeChoice,
)
from deepfellow.common.docker import (
    add_network_to_service,
    ensure_network,
    save_compose_file,
)
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import translate_to_install_error
from deepfellow.common.generate import generate_password
from deepfellow.common.install import assert_docker, ensure_directory
from deepfellow.common.registry import get_newest_image_tag
from deepfellow.common.system import run
from deepfellow.server.utils.configure import configure_infra, configure_mongo, configure_otel, configure_vector_db

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def _is_json_object(value: str) -> bool:
    """Check whether a string parses as a JSON object.

    Args:
        value: The string to parse.

    Returns:
        True if the value is valid JSON with an object at the top level.
    """
    try:
        return isinstance(json.loads(value), dict)
    except json.JSONDecodeError:
        return False


def expose_ports_to_host(services: dict[str, Any]) -> None:
    """Add host port mappings for services that only have 'expose' (no 'ports')."""
    for service in services.values():
        if "expose" in service and "ports" not in service:
            service["ports"] = [f"{port}:{port}" for port in service["expose"]]


@translate_to_install_error
def install(  # noqa: C901
    directory: Path = DF_SERVER_DIRECTORY,
    port: int = DF_SERVER_PORT,
    image: str = DF_SERVER_IMAGE,
    local_image: bool = False,
    otel_url: str | None = None,
    otel_local: bool = False,
    infra_url: str = DF_INFRA_URL,
    infra_api_key: str | None = None,
    docker_network: str = DF_INFRA_DOCKER_NETWORK,
    mongodb_url: str = DF_MONGO_URL,
    mongodb_port: int = DF_MONGO_PORT,
    mongodb_database_name: str = DF_MONGO_DB,
    mongodb_username: str = "",
    mongodb_password: str = "",
    vectordb_active: bool = bool(DEFAULT_VECTOR_DATABASE["provider"]["active"]),
    vectordb_type: VectorDBTypeChoice = VectorDBTypeChoice(DEFAULT_VECTOR_DATABASE_TYPE),
    vectordb_url: str = DEFAULT_VECTOR_DATABASE["provider"]["url"],
    vectordb_database_name: str = MILVUS_DATABASE["provider"]["db"],
    vectordb_username: str = "",
    vectordb_password: str = "",
    embedding_model: str = DEFAULT_VECTOR_DATABASE["embedding"]["model"],
    embedding_size: str = DEFAULT_VECTOR_DATABASE["embedding"]["size"],
    embedding_sparse: bool = False,
    force_install: bool = False,
    dev: bool = False,
) -> None:
    """Install DeepFellow Server with docker."""
    if otel_local and otel_url:
        echo.error("--otel-local and --otel-url are mutually exclusive; pass only one.")
        raise typer.Exit(1)

    echo.info("Installing DeepFellow Server.")
    assert_docker()

    if not local_image and image == DF_SERVER_IMAGE:
        image = get_newest_image_tag(DF_SERVER_IMAGE_HUB)

    ensure_directory(
        directory, error_message="Unable to create DeepFellow Server directory.", force_install=force_install
    )

    env_file = directory / ".env"

    original_env_content = read_env_file_to_dict(env_file)

    log_level = str(original_env_content.get("df_log_level", "INFO")).upper()
    if log_level not in LOG_LEVELS:
        echo.error(f"Invalid DF_LOG_LEVEL in {env_file.as_posix()}: expected one of {', '.join(LOG_LEVELS)}.")
        raise typer.Exit(1)

    plugins_setup = original_env_content.get("df_plugins_setup", "{}")
    if not isinstance(plugins_setup, str) or not _is_json_object(plugins_setup):
        echo.error(f"Invalid DF_PLUGINS_SETUP in {env_file.as_posix()}: expected a single-line JSON object.")
        raise typer.Exit(1)

    # Find out which docker network to use
    docker_network = echo.prompt(
        "Provide a docker network name",
        from_args=docker_network,
        original_default=DF_INFRA_DOCKER_NETWORK,
        default=original_env_content.get("df_infra_docker_subnet", docker_network),
    )

    # Create the network if needed
    ensure_network(docker_network)

    echo.info("DeepFellow Server requires a MongoDB to be installed.")
    if mongodb_url != DF_MONGO_URL or mongodb_database_name != DF_MONGO_DB:
        custom_mongo_db_server = True
    else:
        custom_mongo_db_server = not echo.confirm("Install a local MongoDB for DeepFellow Server?", default=True)

    mongo_env = configure_mongo(
        directory,
        custom_mongo_db_server,
        mongodb_username,
        mongodb_password,
        mongodb_url,
        mongodb_database_name,
        original_env_content,
        mongodb_port,
    )

    echo.info("DeepFellow Server is communicating with DeepFellow Infra.")
    infra_env = configure_infra(infra_api_key, infra_url, original_env_content)

    original_metrics_username = original_env_content.get("df_metrics_username")
    original_metrics_password = original_env_content.get("df_metrics_password")

    if (
        original_metrics_username is not None
        and original_metrics_password is not None
        and echo.confirm("Would you like to keep the previously configured metrics credentials?", default=True)
    ):
        metrics_username = str(original_metrics_username)
        metrics_password = str(original_metrics_password)
    else:
        metrics_username = generate_password(8)
        metrics_password = generate_password(12)

    echo.info("DeepFellow Server might use a vector DB. If not provided some features will not work.")

    # Configure vector database
    is_custom_vector_db_server, vectordb_envs = configure_vector_db(
        infra_env["DF_INFRA__URL"],
        original_env_content,
        int(vectordb_active),
        vectordb_type.value,
        vectordb_url,
        vectordb_database_name,
        vectordb_username,
        vectordb_password,
        embedding_model,
        embedding_size,
        embedding_sparse,
        str(original_env_content.get("df_vector_database__provider__type", vectordb_type.value)),
    )
    is_vectordb_active = vectordb_envs.get("DF_VECTOR_DATABASE__PROVIDER__ACTIVE") == "1"
    vectordb_type_str = vectordb_envs.get("DF_VECTOR_DATABASE__PROVIDER__TYPE", "")

    otel = configure_otel(directory, otel_url, original_env_content, otel_local)

    save_env_file(
        env_file,
        {
            "DF_SERVER_PORT": port,
            "DF_SERVER_URL": f"http://localhost:{port}",
            "DF_SERVER_IMAGE": image,
            "DF_INFRA_DOCKER_SUBNET": docker_network,
            "DF_METRICS_USERNAME": metrics_username,
            "DF_METRICS_PASSWORD": metrics_password,
            "DF_LOG_LEVEL": log_level,
            "DF_PLUGINS_SETUP": plugins_setup,
            **mongo_env,
            **infra_env,
            **vectordb_envs,
            **otel.envs,
        },
    )

    volumes: dict[str, None] = {}
    services: dict[str, Any] = {}
    depends_on = {}
    compose_server = deepcopy(DOCKER_COMPOSE_SERVER)
    # TODO Clean up the `cast` after https://gitlab2.simplito.com/df/df-cli/-/issues/258
    server_docker_envs = cast("list[str]", compose_server["server"]["environment"])

    if is_vectordb_active:
        # Update server's docker environment
        server_docker_envs.extend(DOCKER_COMPOSE_SERVER_VECTOR_DB_ENVS)
        if vectordb_type_str == "milvus":
            server_docker_envs.extend(DOCKER_COMPOSE_SERVER_VECTOR_DB_MILVUS_ENVS)

        # Add vector database docker compose definitions if user did not provided custom fields
        if not is_custom_vector_db_server:
            if vectordb_type_str == "qdrant":
                services.update(DOCKER_COMPOSE_QDRANT)
                volumes.update({"qdrant_data": None})
                depends_on.update({"qdrant": {"condition": "service_started"}})
            else:
                services.update(DOCKER_COMPOSE_MILVUS)
                volumes.update({"milvus": None, "etcd": None, "minio": None})
                depends_on.update({"milvus": {"condition": "service_healthy"}})

            echo.info(f"A default {vectordb_type_str.capitalize()} setup is created.")

    if not custom_mongo_db_server:
        services.update(DOCKER_COMPOSE_MONGO_DB)
        volumes["mongo"] = None
        depends_on.update({"mongo": {"condition": "service_healthy"}})

    environment = cast("list", compose_server["server"]["environment"])
    for api_endpoint_key in infra_env:
        environment.append(api_endpoint_key + "=${" + api_endpoint_key + "}")

    if otel.docker_compose:
        services.update(otel.docker_compose)
        depends_on["otel-collector"] = {"condition": "service_started"}

    if otel.envs.get("DF_OTEL_TRACING_ENABLED") == "true" and otel.envs.get("DF_OTEL_EXPORTER_OTLP_ENDPOINT"):
        environment.append("DF_OTEL_EXPORTER_OTLP_ENDPOINT=${DF_OTEL_EXPORTER_OTLP_ENDPOINT}")
        environment.append("DF_OTEL_TRACING_ENABLED=${DF_OTEL_TRACING_ENABLED}")

    if not is_vectordb_active:
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

    if dev:
        expose_ports_to_host(services)
        echo.warning("Dev mode: internal service ports are exposed to the host. Do not use in production.")

    save_compose_file(
        {"services": services, "volumes": volumes, "networks": {docker_network: {"external": True}}},
        directory / DOCKER_COMPOSE_CONFIG_FILENAME,
    )
    run(["docker", "compose", "pull"], directory)
    echo.success("DeepFellow Server Installed.\nCall `deepfellow server start`.")
