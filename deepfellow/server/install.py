"""Install server typer command."""

from copy import deepcopy
from pathlib import Path
from typing import cast

import typer

from deepfellow.common.config import read_env_file_to_dict, save_env_file
from deepfellow.common.defaults import (
    DF_INFRA_DOCKER_NETWORK,
    DF_SERVER_IMAGE,
    DF_SERVER_PORT,
    DF_SERVER_STORAGE_DIRECTORY,
)
from deepfellow.common.docker import (
    COMPOSE_MONGO_DB,
    COMPOSE_SERVER,
    COMPOSE_VECTOR_DB,
    add_network_to_service,
    ensure_network,
    save_compose_file,
)
from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker, ensure_directory
from deepfellow.common.system import run
from deepfellow.server.utils.configure import (
    configure_infra,
    configure_mongo,
    configure_vector_db,
)
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def install(
    directory: Path = directory_option("Target directory for the DeepFellow Server installation."),
    port: int = typer.Option(
        DF_SERVER_PORT, envvar="DF_SERVER_PORT", help="Port to use to serve the DeepFellow Server from."
    ),
    image: str = typer.Option(DF_SERVER_IMAGE, envvar="DF_SERVER_IMAGE", help="DeepFellow Server docker image."),
) -> None:
    """Install DeepFellow Server with docker."""
    echo.info("Installing DeepFellow Server.")

    assert_docker()

    ensure_directory(directory, error_message="Unable to create DeepFellow Server directory.")

    env_file = directory / ".env"
    original_env_content = read_env_file_to_dict(env_file)

    echo.info("DeepFellow Server requires a MongoDB to be installed.")
    custom_mongo_db_server = echo.confirm("Do you have MongoDB installed for DeepFellow Server?")
    mongo_env = configure_mongo(custom_mongo_db_server, original_env_content)

    echo.info("DeepFellow Server is communicating with DeepFellow Infra.")
    infra_env = configure_infra()

    # Find out which docker network to use
    docker_network = echo.prompt("Provide a docker network name", default=DF_INFRA_DOCKER_NETWORK)

    # Create the network if needed
    ensure_network(docker_network)

    echo.info("DeepFellow Server might use a vector DB. If not provided some features will not work.")
    custom_vector_db_server = echo.confirm("Do you have a vector DB ready?")
    vector_db_envs = configure_vector_db(custom_vector_db_server, infra_env["DF_INFRA__URL"], original_env_content)
    vector_db_active = vector_db_envs.get("DF_VECTOR_DATABASE__PROVIDER__ACTIVE") == "1"

    save_env_file(
        env_file,
        {
            "DF_SERVER_PORT": port,
            "DF_SERVER_IMAGE": image,
            "DF_INFRA_DOCKER_SUBNET": docker_network,
            **mongo_env,
            **infra_env,
            **vector_db_envs,
        },
    )

    volumes: dict[str, None] = {}
    services = {}
    depends_on = {}

    if not custom_vector_db_server and vector_db_active:
        services.update(COMPOSE_VECTOR_DB)
        volumes.update({"milvus": None, "etcd": None, "minio": None})
        depends_on.update({"milvus": {"condition": "service_healthy"}})

    if not custom_mongo_db_server:
        services.update(COMPOSE_MONGO_DB)
        volumes["mongo"] = None
        depends_on.update({"mongo": {"condition": "service_healthy"}})

    compose_server = deepcopy(COMPOSE_SERVER)
    environment = cast("list", compose_server["server"]["environment"])
    for api_endpoint_key in infra_env:
        environment.append(api_endpoint_key + "=${" + api_endpoint_key + "}")

    if depends_on:
        compose_server["server"]["depends_on"] = depends_on

    if not vector_db_active:
        compose_server["server"]["environment"] = [
            env for env in environment if not env.startswith("DF_VECTOR_DATABASE__") or "ACTIVE" in env
        ]

    services.update(compose_server)

    for _, service in services.items():
        add_network_to_service(service, docker_network)

    services["server"]["volumes"] = [f"{DF_SERVER_STORAGE_DIRECTORY}:/app/storage"]

    save_compose_file(
        {"services": services, "volumes": volumes, "networks": {docker_network: {"external": True}}},
        directory / "docker-compose.yml",
    )
    run("docker compose pull", directory)
    echo.success("DeepFellow Server Installed.\nCall `deepfellow server start`.")
