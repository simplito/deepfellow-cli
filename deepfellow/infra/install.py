"""Install infra typer command."""

import random
import string
from pathlib import Path
from typing import Any

import typer

from deepfellow.common.config import configure_uuid_key, env_to_dict, read_env_file, save_env_file
from deepfellow.common.defaults import (
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_IMAGE,
    DF_INFRA_PORT,
    DF_INFRA_STORAGE_DIR,
)
from deepfellow.common.docker import COMPOSE_INFRA, ensure_network, find_docker_config, get_socket, save_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def install(
    ctx: typer.Context,
    directory: Path = directory_option("Target directory for the Infra installation."),
    port: int = typer.Option(DF_INFRA_PORT, envvar="DF_INFRA_PORT", help="Port to use to serve the Infra from."),
    image: str = typer.Option(DF_INFRA_IMAGE, envvar="DF_INFRA_IMAGE", help="Infra docker image."),
    docker_network: str = typer.Option(
        DF_INFRA_DOCKER_NETWORK, envvar="DF_INFRA_DOCKER_NETWORK", help="Infra docker network."
    ),
    docker_config: Path | None = typer.Option(None, envvar="DF_INFRA_DOCKER_CONFIG", help="Path to the docker config."),
    storage: Path = typer.Option(
        DF_INFRA_STORAGE_DIR, envvar="DF_INFRA_STORAGE_DIR", help="Storage for the Infra services."
    ),
    hugging_face_api_key: str | None = typer.Option(
        None, envvar="DF_HUGGING_FACE_API_KEY", help="Hugging Face API Key"
    ),
    civitai_token: str | None = typer.Option(None, envvar="DF_CIVITAI_TOKEN", help="Civitai Token"),
) -> None:
    """Install infra with docker."""
    yes = ctx.obj.get("yes", False)
    echo.debug(f"{directory=},\n{yes=}")

    # Retrieve the docker info to fail early in the process in docker is not running or configured differently
    docker_socket = get_socket()
    try:
        docker_config = find_docker_config(explicit_path=docker_config)
    except FileNotFoundError as exc:
        echo.error("Docker configuration file not found.\nUse --docker-config option to provide it.")
        raise typer.Exit(1) from exc

    # Check if overriding existing installation
    override_existing_installation = False
    directory_exists = False
    if directory.is_dir():
        directory_exists = True
        echo.warning(f"Directory {directory} already exists.")
        override_existing_installation = echo.confirm("Should I override existing installation?")
        if not override_existing_installation:
            raise typer.Exit(1)

    echo.info("Installing DeepFellow Infra.")
    if not directory_exists:
        try:
            directory.mkdir(parents=True)
        except Exception as exc_info:
            echo.error("Unable to create infra directory.")
            reraise_if_debug(exc_info)

    # Prepare the starting point for .env
    env_file = directory / ".env"
    original_env_content: dict[str, Any] = {}
    if env_file.exists():
        original_env_vars = read_env_file(env_file)
        original_env_content = env_to_dict(original_env_vars)

    # Collect DF_INFRA_API_KEY
    echo.info("A DeepFellow Server or other infra needs to identify in DeepFellow Infra by providing an API Key.")
    api_key = configure_uuid_key("API Key", original_env_content.get("df_infra_api_key"))

    echo.info("An Admin needs to identify itself in DeepFellow Infra to perform actions.")
    admin_api_key = configure_uuid_key("Admin API Key", original_env_content.get("df_infra_admin_api_key"))

    # Find out which docker network to use
    original_docker_network = original_env_content.get("df_infra_docker_subnet")
    if (
        original_docker_network is not None
        and original_docker_network != DF_INFRA_DOCKER_NETWORK
        and docker_network == DF_INFRA_DOCKER_NETWORK
        and echo.confirm(
            f"Would you like to keep the previously configured docker network '{original_docker_network}'?",
            default=True,
        )
    ):
        docker_network = original_docker_network

    # Create the network if needed
    ensure_network(docker_network)

    # Find out the compose prefix
    original_compose_prefix = original_env_content.get("df_infra_compose_prefix")
    compose_prefix: str | None = None
    if original_compose_prefix is not None and echo.confirm(
        f"Would you like to keep the previously configured compose prefix '{original_compose_prefix}'?", default=True
    ):
        compose_prefix = original_compose_prefix
    else:
        random_letters = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        compose_prefix = f"df{random_letters}_"

    # Find out the infra storage dir
    original_storage = original_env_content.get("DF_INFRA_STORAGE_DIR")
    if (
        original_storage is not None
        and original_storage != DF_INFRA_STORAGE_DIR
        and storage == DF_INFRA_STORAGE_DIR
        and echo.confirm(
            f"Would you like to keep the previously configured storage dir '{original_storage}'?",
            default=True,
        )
    ):
        storage = original_storage

    # Save the envs to the .env file (existing envs are NOT overwritten)
    infra_values = {
        "DF_INFRA_PORT": port,
        "DF_INFRA_IMAGE": image,
        "DF_INFRA_API_KEY": api_key,
        "DF_INFRA_ADMIN_API_KEY": admin_api_key,
        "DF_INFRA_DOCKER_SUBNET": docker_network,
        "DF_INFRA_COMPOSE_PREFIX": compose_prefix,
        "DF_INFRA_DOCKER_CONFIG": str(docker_config),
        "DF_INFRA_STORAGE_DIR": storage.expanduser().resolve().as_posix(),
        "DF_HUGGING_FACE_API_KEY": (
            hugging_face_api_key if hugging_face_api_key else echo.prompt("Provide an optional Hugging Face API Key")
        ),
        "DF_CIVITAI_TOKEN": (
            civitai_token if civitai_token is not None else echo.prompt("Provide an optional Civitai Token")
        ),
    }
    save_env_file(env_file, infra_values)

    # Save the docker compose config
    compose_infra = COMPOSE_INFRA
    compose_infra["infra"]["volumes"].append(f"{docker_socket}:/run/docker.sock")
    save_compose_file(
        {"services": compose_infra, "networks": {docker_network: {"external": True}}},
        directory / "docker-compose.yml",
    )

    echo.success("DeepFellow Infra installed.\nCall `depfellow infra start`.")
