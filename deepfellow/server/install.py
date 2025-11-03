"""Install server typer command."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import typer

from deepfellow.common.config import configure_uuid_key, env_to_dict, read_env_file, save_env_file
from deepfellow.common.defaults import DF_SERVER_IMAGE, DF_SERVER_PORT
from deepfellow.common.docker import COMPOSE_MONGO_DB, COMPOSE_SERVER, COMPOSE_VECTOR_DB, save_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
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
    ctx: typer.Context,
    directory: Path = directory_option("Target directory for the DeepFellow Server installation."),
    port: int = typer.Option(
        DF_SERVER_PORT, envvar="DF_SERVER_PORT", help="Port to use to serve the DeepFellow Server from."
    ),
    image: str = typer.Option(DF_SERVER_IMAGE, envvar="DF_SERVER_IMAGE", help="DeepFellow Server docker image."),
) -> None:
    """Install DeepFellow Server with docker."""
    yes = ctx.obj.get("yes", False)
    echo.debug(f"{directory=},\n{yes=}")
    override_existing_installation = False
    directory_exists = False
    if directory.is_dir():
        directory_exists = True
        echo.warning(f"Directory {directory} already exists.")
        override_existing_installation = echo.confirm("Should I override existing installation?")
        if not override_existing_installation:
            raise typer.Exit(1)

    echo.info("Installing DeepFellow Server.")
    if not directory_exists:
        try:
            directory.mkdir(parents=True)
        except Exception as exc_info:
            echo.error("Unable to create DeepFellow Server directory.")
            reraise_if_debug(exc_info)

    env_file = directory / ".env"
    original_env_content: dict[str, Any] = {}
    if env_file.exists():
        original_env_vars = read_env_file(env_file)
        original_env_content = env_to_dict(original_env_vars)

    echo.info("DeepFellow Server requires a MongoDB to be installed.")
    custom_mongo_db_server = echo.confirm("Do you have MongoDB installed for DeepFellow Server?")
    mongo_env = configure_mongo(custom_mongo_db_server, original_env_content)

    echo.info("DeepFellow Server is communicating with DeepFellow Infra.")
    infra_env = configure_infra(original_env_content)

    echo.info("DeepFellow Server might use a vector DB. If not provided some features will not work.")
    custom_vector_db_server = echo.confirm("Do you have a vector DB ready?")
    vector_db_envs = configure_vector_db(custom_vector_db_server, infra_env["DF_INFRA__URL"], original_env_content)
    vector_db_active = vector_db_envs.get("DF_VECTOR_DATABASE__PROVIDER__ACTIVE") == "1"

    save_env_file(
        env_file,
        {
            "DF_SERVER_PORT": port,
            "DF_SERVER_IMAGE": image,
            **mongo_env,
            **infra_env,
            **vector_db_envs,
        },
    )

    volumes = {}

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
    for api_endpoint_key in infra_env:
        compose_server["server"]["environment"].append(api_endpoint_key + "=${" + api_endpoint_key + "}")

    if depends_on:
        compose_server["server"]["depends_on"] = depends_on

    services.update(compose_server)

    save_compose_file({"services": services, "volumes": volumes}, directory / "docker-compose.yml")
    run("docker compose pull", directory)
    echo.success("DeepFellow Server Installed.\nCall `deepfellow server start`.")
