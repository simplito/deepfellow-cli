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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import typer

from deepfellow.common.config import (
    EnvDict,
    read_env_file_to_dict,
    save_env_file,
)
from deepfellow.common.defaults import (
    DEFAULT_VECTOR_DATABASE,
    DEFAULT_VECTOR_DATABASE_TYPE,
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_URL,
    DF_MONGO_DB,
    DF_MONGO_PORT,
    DF_MONGO_URL,
    DF_NEO4J_URI,
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
    DOCKER_COMPOSE_SERVER_NEO4J_ENVS,
    DOCKER_COMPOSE_SERVER_VECTOR_DB_ENVS,
    DOCKER_COMPOSE_SERVER_VECTOR_DB_MILVUS_ENVS,
    MILVUS_DATABASE,
    VectorDBTypeChoice,
)
from deepfellow.common.docker import (
    DockerError,
    add_network_to_service,
    ensure_network,
    save_compose_file,
)
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug, translate_to_install_error
from deepfellow.common.generate import generate_password
from deepfellow.common.install import assert_docker, ensure_directory
from deepfellow.common.registry import get_newest_image_tag
from deepfellow.common.system import run
from deepfellow.server.utils.configure import (
    Neo4jConfig,
    OtelConfig,
    configure_infra,
    configure_mongo,
    configure_neo4j,
    configure_otel,
    configure_vector_db,
)

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
    except (ValueError, TypeError, RecursionError):
        return False


def expose_ports_to_host(services: dict[str, Any]) -> None:
    """Add host port mappings for services that only have 'expose' (no 'ports')."""
    for service in services.values():
        if "expose" in service and "ports" not in service:
            service["ports"] = [f"{port}:{port}" for port in service["expose"]]


@dataclass
class InstallContext:
    """Read-only values gathered from the environment before any prompting."""

    directory: Path
    newest_image_tag: str | None
    original_env_content: EnvDict
    log_level: str
    plugins_setup: str


def inspect(directory: Path, image: str, local_image: bool, force_install: bool) -> InstallContext:
    """Docker check, directory creation, existing .env read-back + validation.

    No prompts, no network/compose writes.

    Returns:
        InstallContext: Read-only values needed by :func:`resolve`.
    """
    assert_docker()
    ensure_directory(
        directory, error_message="Unable to create DeepFellow Server directory.", force_install=force_install
    )
    newest_image_tag = (
        get_newest_image_tag(DF_SERVER_IMAGE_HUB) if not local_image and image == DF_SERVER_IMAGE else None
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

    return InstallContext(directory, newest_image_tag, original_env_content, log_level, plugins_setup)


@dataclass
class InstallConfig:
    """Final, fully-resolved installation values, ready to be persisted."""

    directory: Path
    port: int
    image: str
    docker_network: str
    log_level: str
    plugins_setup: str
    metrics_username: str
    metrics_password: str
    mongo_env: dict[str, str]
    custom_mongo_db_server: bool
    infra_env: dict[str, Any]
    vectordb_envs: dict[str, str]
    is_vectordb_active: bool
    is_custom_vector_db_server: bool
    vectordb_type: str
    otel: OtelConfig
    neo4j: Neo4jConfig
    local_image: bool
    dev: bool


def resolve(
    context: InstallContext,
    *,
    port: int,
    image: str,
    otel_url: str | None,
    otel_local: bool,
    infra_url: str,
    infra_api_key: str | None,
    docker_network: str,
    mongodb_url: str,
    mongodb_port: int,
    mongodb_database_name: str,
    mongodb_username: str,
    mongodb_password: str,
    vectordb_active: bool,
    vectordb_type: VectorDBTypeChoice,
    vectordb_url: str,
    vectordb_database_name: str,
    vectordb_username: str,
    vectordb_password: str,
    embedding_model: str,
    embedding_size: str,
    embedding_sparse: bool,
    neo4j_active: bool,
    neo4j_url: str,
    neo4j_username: str,
    neo4j_password: str,
    local_image: bool,
    dev: bool,
) -> InstallConfig:
    """Prompt the user for / apply CLI overrides to the remaining install values.

    Args:
        context: Read-only values gathered by :func:`inspect`.
        port: Published port to serve the DeepFellow Server from.
        image: DeepFellow Server docker image, before newest-tag resolution.
        otel_url: Existing Open Telemetry collector URL, if any.
        otel_local: Whether to install a local debug-only Open Telemetry collector.
        infra_url: DeepFellow Infra URL to connect to.
        infra_api_key: DeepFellow Infra API key.
        docker_network: Requested docker network name.
        mongodb_url: Requested MongoDB connection URL.
        mongodb_port: Host port to publish a locally managed MongoDB on.
        mongodb_database_name: Requested MongoDB database name.
        mongodb_username: Requested MongoDB username.
        mongodb_password: Requested MongoDB password.
        vectordb_active: Whether a vector database should be configured.
        vectordb_type: Requested vector database type.
        vectordb_url: Requested vector database connection URL.
        vectordb_database_name: Requested vector database database/collection name.
        vectordb_username: Requested vector database username.
        vectordb_password: Requested vector database password.
        embedding_model: Requested embedding model.
        embedding_size: Requested embedding size.
        embedding_sparse: Whether to use sparse embeddings.
        neo4j_active: Whether the Knowledge Graph's Neo4j instance should be configured.
        neo4j_url: Requested Neo4j connection URI.
        neo4j_username: Requested Neo4j username.
        neo4j_password: Requested Neo4j password.
        local_image: Whether a locally built docker image is used.
        dev: Whether to expose internal service ports to the host.

    Returns:
        InstallConfig: The fully-resolved installation configuration.
    """
    directory = context.directory
    original_env_content = context.original_env_content

    # Find out which docker network to use
    docker_network = echo.prompt(
        "Provide a docker network name",
        from_args=docker_network,
        original_default=DF_INFRA_DOCKER_NETWORK,
        default=original_env_content.get("df_infra_docker_subnet", docker_network),
    )

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

    neo4j = configure_neo4j(neo4j_active, neo4j_url, neo4j_username, neo4j_password, original_env_content)

    return InstallConfig(
        directory=directory,
        port=port,
        image=context.newest_image_tag or image,
        docker_network=docker_network,
        log_level=context.log_level,
        plugins_setup=context.plugins_setup,
        metrics_username=metrics_username,
        metrics_password=metrics_password,
        mongo_env=mongo_env,
        custom_mongo_db_server=custom_mongo_db_server,
        infra_env=infra_env,
        vectordb_envs=vectordb_envs,
        is_vectordb_active=is_vectordb_active,
        is_custom_vector_db_server=is_custom_vector_db_server,
        vectordb_type=vectordb_type_str,
        otel=otel,
        neo4j=neo4j,
        local_image=local_image,
        dev=dev,
    )


def apply(config: InstallConfig) -> None:  # noqa: C901
    """Create the docker network, write the .env/compose files, and pull the image.

    Purely programmatic: no prompts, so it does not leave a half-configured
    installation behind if an earlier phase (:func:`resolve`) was interrupted.
    """
    # Create the network if needed
    ensure_network(config.docker_network)

    save_env_file(
        config.directory / ".env",
        {
            "DF_SERVER_PORT": config.port,
            "DF_SERVER_URL": f"http://localhost:{config.port}",
            "DF_SERVER_IMAGE": config.image,
            "DF_INFRA_DOCKER_SUBNET": config.docker_network,
            "DF_METRICS_USERNAME": config.metrics_username,
            "DF_METRICS_PASSWORD": config.metrics_password,
            "DF_LOG_LEVEL": config.log_level,
            "DF_PLUGINS_SETUP": config.plugins_setup,
            **config.mongo_env,
            **config.infra_env,
            **config.vectordb_envs,
            **config.otel.envs,
            **config.neo4j.envs,
        },
    )

    volumes: dict[str, None] = {}
    services: dict[str, Any] = {}
    depends_on = {}
    compose_server = deepcopy(DOCKER_COMPOSE_SERVER)
    # TODO Clean up the `cast` after https://gitlab2.simplito.com/df/df-cli/-/issues/258
    server_docker_envs = cast("list[str]", compose_server["server"]["environment"])

    if config.is_vectordb_active:
        # Update server's docker environment
        server_docker_envs.extend(DOCKER_COMPOSE_SERVER_VECTOR_DB_ENVS)
        if config.vectordb_type == "milvus":
            server_docker_envs.extend(DOCKER_COMPOSE_SERVER_VECTOR_DB_MILVUS_ENVS)

        # Add vector database docker compose definitions if user did not provide custom fields
        if not config.is_custom_vector_db_server:
            if config.vectordb_type == "qdrant":
                services.update(deepcopy(DOCKER_COMPOSE_QDRANT))
                volumes.update({"qdrant_data": None})
                depends_on.update({"qdrant": {"condition": "service_started"}})
            else:
                services.update(deepcopy(DOCKER_COMPOSE_MILVUS))
                volumes.update({"milvus": None, "etcd": None, "minio": None})
                depends_on.update({"milvus": {"condition": "service_healthy"}})

            echo.info(f"A default {config.vectordb_type.capitalize()} setup is created.")

    if not config.custom_mongo_db_server:
        services.update(deepcopy(DOCKER_COMPOSE_MONGO_DB))
        volumes["mongo"] = None
        depends_on.update({"mongo": {"condition": "service_healthy"}})

    environment = cast("list", compose_server["server"]["environment"])
    for api_endpoint_key in config.infra_env:
        environment.append(api_endpoint_key + "=${" + api_endpoint_key + "}")

    if config.otel.docker_compose:
        services.update(deepcopy(config.otel.docker_compose))
        depends_on["otel-collector"] = {"condition": "service_started"}

    if config.neo4j.docker_compose:
        services.update(deepcopy(config.neo4j.docker_compose))
        volumes["neo4j_data"] = None
        depends_on["neo4j"] = {"condition": "service_healthy"}

    if config.neo4j.envs.get("DF_GRAPHITI__ENABLED") == "true":
        server_docker_envs.extend(DOCKER_COMPOSE_SERVER_NEO4J_ENVS)

    if config.otel.envs.get("DF_OTEL_TRACING_ENABLED") == "true" and config.otel.envs.get(
        "DF_OTEL_EXPORTER_OTLP_ENDPOINT"
    ):
        environment.append("DF_OTEL_EXPORTER_OTLP_ENDPOINT=${DF_OTEL_EXPORTER_OTLP_ENDPOINT}")
        environment.append("DF_OTEL_TRACING_ENABLED=${DF_OTEL_TRACING_ENABLED}")

    if not config.is_vectordb_active:
        compose_server["server"]["environment"] = [
            env for env in environment if not env.startswith("DF_VECTOR_DATABASE__") or "ACTIVE" in env
        ]

    if depends_on:
        compose_server["server"]["depends_on"] = depends_on

    if config.local_image:
        compose_server["server"]["pull_policy"] = "never"

    services.update(compose_server)

    for _, service in services.items():
        add_network_to_service(service, config.docker_network)

    # Create directories for plugins and storage so Docker never has to auto-create these
    # bind-mount sources itself (which it would do as root, breaking later writes as this user).
    plugins_directory = config.directory / "plugins"
    try:
        plugins_directory.mkdir(exist_ok=True)
    except OSError as exc:
        echo.error(f"Unable to create {plugins_directory}: {exc}.")
        reraise_if_debug(exc)
    try:
        DF_SERVER_STORAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        echo.error(f"Unable to create {DF_SERVER_STORAGE_DIRECTORY}: {exc}.")
        reraise_if_debug(exc)

    services["server"]["volumes"] = [
        f"{DF_SERVER_STORAGE_DIRECTORY}:/app/storage",
        f"{plugins_directory.as_posix()}:/app/plugins",
    ]

    if config.dev:
        expose_ports_to_host(services)
        echo.warning("Dev mode: internal service ports are exposed to the host. Do not use in production.")

    save_compose_file(
        {"services": services, "volumes": volumes, "networks": {config.docker_network: {"external": True}}},
        config.directory / DOCKER_COMPOSE_CONFIG_FILENAME,
    )
    try:
        run(["docker", "compose", "pull"], config.directory, raises=DockerError)
    except DockerError as exc:
        echo.error(f"Failed to pull docker image(s): {exc}\nCheck registry access, credentials, and disk space.")
        raise typer.Exit(1) from exc
    echo.success("DeepFellow Server Installed.\nCall `deepfellow server start`.")


@translate_to_install_error
def install(
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
    neo4j_active: bool = False,
    neo4j_url: str = DF_NEO4J_URI,
    neo4j_username: str = "",
    neo4j_password: str = "",
    force_install: bool = False,
    dev: bool = False,
) -> None:
    """Install DeepFellow Server with docker."""
    if otel_local and otel_url:
        echo.error("--otel-local and --otel-url are mutually exclusive; pass only one.")
        raise typer.Exit(1)

    echo.info("Installing DeepFellow Server.")

    context = inspect(directory=directory, image=image, local_image=local_image, force_install=force_install)

    config = resolve(
        context,
        port=port,
        image=image,
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
        local_image=local_image,
        dev=dev,
    )

    apply(config)
