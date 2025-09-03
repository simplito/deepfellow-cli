"""Install server typer command."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import typer

from deepfellow.common.config import configure_uuid_key, env_to_dict, read_env_file, save_env_file
from deepfellow.common.defaults import DF_SERVER_DIRECTORY, DF_SERVER_IMAGE, DF_SERVER_PORT
from deepfellow.common.docker import COMPOSE_MONGO_DB, COMPOSE_SERVER, COMPOSE_VECTOR_DB, save_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.server.utils.configure import (
    configure_infras,
    configure_mongo,
    configure_vector_db,
)

app = typer.Typer()


@app.command()
def install(
    ctx: typer.Context,
    directory: Path = typer.Option(
        DF_SERVER_DIRECTORY,
        "--directory",
        "--dir",
        envvar="DF_SERVER_DIRECTORY",
        help="Target directory for the DFServer installation.",
    ),
    port: int = typer.Option(DF_SERVER_PORT, envvar="DF_INFRA_PORT", help="Port to use to serve the DFServer from."),
    image: str = typer.Option(DF_SERVER_IMAGE, envvar="DF_INFRA_IMAGE", help="DFServer docker image."),
) -> None:
    """Install DFServer with docker."""
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

    echo.info("Installing DF Server.")
    if not directory_exists:
        try:
            directory.mkdir(parents=True)
        except Exception as exc_info:
            echo.error("Unable to create DF Server directory.")
            reraise_if_debug(exc_info)

    env_file = directory / ".env"
    original_env_content: dict[str, Any] = {}
    if env_file.exists():
        original_env_vars = read_env_file(env_file)
        original_env_content = env_to_dict(original_env_vars)

    echo.info("DF Server requires a MongoDB to be installed.")
    custom_mongo_db_server = echo.confirm("Do you have MongoDB installed for DF Server?")
    mongo_env = configure_mongo(custom_mongo_db_server)

    echo.info("DF Server is communicating with infra. At least one needs to exist.")
    api_endpoints = configure_infras()
    api_endpoints_env = api_endpoints.envs

    echo.info("DF Server might use a vector DB. If not provided some features will not work.")
    custom_vector_db_server = echo.confirm("Do you have a vector DB ready?")
    vector_db_envs = configure_vector_db(custom_vector_db_server, api_endpoints.names)
    vector_db_active = vector_db_envs.get("DF_VECTOR_DATABASE__PROVIDER__ACTIVE") == "1"

    echo.info("An Admin needs to identify in DF Server by providing an Admin Key.")
    admin_key_env = configure_uuid_key("Admin Key", original_env_content.get("df_admin_key"))

    save_env_file(
        env_file,
        {
            "DF_SERVER_ADMIN_KEY": admin_key_env,
            "DF_SERVER_PORT": port,
            "DF_SERVER_IMAGE": image,
            **mongo_env,
            **api_endpoints_env,
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
    for api_endpoint_key in api_endpoints_env:
        compose_server["server"]["environment"].append(api_endpoint_key + "=${" + api_endpoint_key + "}")

    if depends_on:
        compose_server["server"]["depends_on"] = depends_on

    services.update(compose_server)

    save_compose_file({"services": services, "volumes": volumes}, directory / "docker-compose.yml")
    echo.success("DF Server Installed.\nCall `deepfellow server start`.")
