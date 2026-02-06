# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install infra typer command."""

import random
import string
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import typer

from deepfellow.common.config import (
    configure_uuid_key,
    read_env_file_to_dict,
    save_env_file,
)
from deepfellow.common.defaults import (
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_IMAGE,
    DF_INFRA_NAME,
    DF_INFRA_PORT,
    DF_INFRA_STORAGE_DIR,
    DF_INFRA_URL,
    DOCKER_COMPOSE_INFRA,
)
from deepfellow.common.docker import (
    add_network_to_service,
    ensure_network,
    get_socket,
    save_compose_file,
)
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.generate import generate_password
from deepfellow.common.install import assert_docker, ensure_directory
from deepfellow.common.system import run
from deepfellow.common.validation import validate_df_name, validate_url
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def install(  # noqa: C901
    ctx: typer.Context,
    directory: Path = directory_option("Target directory for the DeepFellow Infra installation."),
    port: int = typer.Option(
        DF_INFRA_PORT, envvar="DF_INFRA_PORT", help="Published port to serve the DeepFellow Infra from."
    ),
    image: str = typer.Option(DF_INFRA_IMAGE, envvar="DF_INFRA_IMAGE", help="DeepFellow Infra docker image."),
    local_image: bool = typer.Option(False, help="Use locally build DeepFellow Infra docker image."),
    docker_config: Path | None = typer.Option(None, envvar="DF_INFRA_DOCKER_CONFIG", help="Path to the docker config."),
    storage: Path = typer.Option(
        DF_INFRA_STORAGE_DIR, envvar="DF_INFRA_STORAGE_DIR", help="Storage for the DeepFellow Infra services."
    ),
    hugging_face_token: str | None = typer.Option(None, envvar="DF_HUGGING_FACE_TOKEN", help="Hugging Face Token"),
    civitai_token: str | None = typer.Option(None, envvar="DF_CIVITAI_TOKEN", help="Civitai Token"),
    infra_name: str = typer.Option(DF_INFRA_NAME, help="Deepfellow Infra name"),
    infra_url: str = typer.Option(DF_INFRA_URL, envvar="DF_INFRA_URL", help="Deepfellow Infra URL"),
    docker_network: str = typer.Option(
        DF_INFRA_DOCKER_NETWORK, envvar="DF_INFRA_DOCKER_NETWORK", help="Docker network"
    ),
    force_install: bool = typer.Option(False, help="Force install"),
) -> None:
    """Install infra with docker."""
    # Retrieve the docker info to fail early in the process in docker is not running or configured differently
    echo.info("Installing DeepFellow Infra.")

    assert_docker()

    docker_socket = get_socket()

    config_file = ctx.obj.get("cli-config-file")
    secrets_file = ctx.obj.get("cli-secrets-file")

    # Check if overriding existing installation
    ensure_directory(
        directory, error_message="Unable to create DeepFellow Infra directory.", force_install=force_install
    )

    # Create empty docker config if needed
    docker_config = docker_config or directory / "docker-config.json"
    if not docker_config.is_file():
        docker_config.write_text("{}", encoding="utf-8")

    # Prepare the starting point for .env
    env_file = directory / ".env"
    original_env_content = read_env_file_to_dict(env_file)

    df_name = echo.prompt(
        "Provide a DF_NAME for this Infra",
        validation=validate_df_name,
        from_args=infra_name,
        original_default=DF_INFRA_NAME,
        default=original_env_content.get("df_infra_name", infra_name),
    )

    df_infra_url = echo.prompt_until_valid(
        "Provide a DF_INFRA_URL for this Infra",
        validate_url,
        error_message="Invalid DF_INFRA_URL. Please try again.",
        from_args=infra_url,
        original_default=DF_INFRA_URL,
        default=original_env_content.get("df_infra_url", infra_url),
    )

    flag_print_keys = echo.confirm("Is it safe to print API keys here?")

    # Collect DF_INFRA_ADMIN_API_KEY
    echo.info("Configuration of DF_INFRA_ADMIN_API_KEY\nkey required for an admin identify in DeepFellow Infra.")
    df_infra_admin_api_key = configure_uuid_key(
        "DF_INFRA_ADMIN_API_KEY", original_env_content.get("df_infra_admin_api_key")
    )
    if flag_print_keys:
        echo.info(f"DF_INFRA_ADMIN_API_KEY: {df_infra_admin_api_key}")

    # Collect DF_INFRA_API_KEY
    echo.info(
        "Configuration of DF_INFRA_API_KEY\nkey needed to communication between DeepFellow Infra and DeepFellow Server."
    )
    df_infra_api_key = configure_uuid_key("DF_INFRA_API_KEY", original_env_content.get("df_infra_api_key"))
    if flag_print_keys:
        echo.info(f"DF_INFRA_API_KEY: {df_infra_api_key}")

    # Collect DF_MESH_KEY
    echo.info(
        "Configuration of DF_MESH_KEY\n"
        "key needed by other DeepFellow Infra to attach to this DeepFellow Infra and thus extend the Mesh."
    )
    df_mesh_key = configure_uuid_key("DF_MESH_KEY", original_env_content.get("df_mesh_key"))
    if flag_print_keys:
        echo.info(f"DF_MESH_KEY: {df_mesh_key}")

    # Find out which docker network to use
    docker_network = echo.prompt(
        "Provide a docker network name",
        from_args=docker_network,
        original_default=DF_INFRA_DOCKER_NETWORK,
        default=original_env_content.get("df_infra_docker_subnet", docker_network),
    )

    # Create the network if needed
    ensure_network(docker_network)

    # Find out the compose prefix
    original_compose_prefix = original_env_content.get("df_infra_compose_prefix")
    compose_prefix = None
    if original_compose_prefix is not None and echo.confirm(
        f"Would you like to keep the previously configured compose prefix '{original_compose_prefix}'?", default=True
    ):
        compose_prefix = original_compose_prefix
    else:
        random_letters = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        compose_prefix = f"df{random_letters}_"

    # Find out the infra storage dir
    original_storage: Any = original_env_content.get("DF_INFRA_STORAGE_DIR")
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

    original_metrics_username = original_env_content.get("df_metrics_username")
    original_metrics_password = original_env_content.get("df_metrics_password")

    if (
        original_metrics_username is not None
        and original_metrics_password is not None
        and echo.confirm("Would you like to keep the previously configured metrics credentials?", default=True)
    ):
        metrics_username = original_metrics_username
        metrics_password = original_metrics_password
    else:
        metrics_username = generate_password(8)
        metrics_password = generate_password(12)

    # Save the envs to the .env file (existing envs are NOT overwritten)
    infra_values = {
        "DF_NAME": df_name,
        "DF_INFRA_URL": df_infra_url,
        "DF_INFRA_PORT": port,
        "DF_INFRA_IMAGE": image,
        "DF_MESH_KEY": df_mesh_key,
        "DF_INFRA_API_KEY": df_infra_api_key,
        "DF_INFRA_ADMIN_API_KEY": df_infra_admin_api_key,
        "DF_CONNECT_TO_MESH_URL": "",
        "DF_CONNECT_TO_MESH_KEY": "",
        "DF_INFRA_DOCKER_SUBNET": docker_network,
        "DF_INFRA_COMPOSE_PREFIX": compose_prefix,
        "DF_INFRA_DOCKER_CONFIG": str(docker_config),
        "DF_INFRA_STORAGE_DIR": storage.expanduser().resolve().as_posix(),
        "DF_METRICS_USERNAME": metrics_username,
        "DF_METRICS_PASSWORD": metrics_password,
    }

    hugging_face_token = hugging_face_token or echo.prompt(
        "Provide an optional Hugging Face Token",
        from_args=hugging_face_token,
        original_default=None,
        default=original_env_content.get("df_hugging_face_token", hugging_face_token) or "",
        password=True,
    )
    if hugging_face_token:
        infra_values["DF_HUGGING_FACE_TOKEN"] = hugging_face_token

    civitai_token = civitai_token or echo.prompt(
        "Provide an optional Civitai Token",
        from_args=civitai_token,
        original_default=None,
        default=original_env_content.get("df_civitai_token", civitai_token) or "",
        password=True,
    )
    if civitai_token:
        infra_values["DF_CIVITAI_TOKEN"] = civitai_token

    save_env_file(env_file, infra_values)
    env_set(config_file, "DF_INFRA_EXTERNAL_URL", f"http://localhost:{port}", should_raise=False)
    env_set(secrets_file, "DF_INFRA_ADMIN_API_KEY", df_infra_admin_api_key, should_raise=False)

    # Save the docker compose config
    compose = deepcopy(DOCKER_COMPOSE_INFRA)
    infra_service = compose["infra"]
    add_network_to_service(infra_service, docker_network)

    volumes = cast("list", infra_service["volumes"])
    volumes.append(f"{docker_socket}:/run/docker.sock")
    volumes.append(f"{docker_socket}:/var/run/docker.sock")
    volumes.append("${DF_INFRA_STORAGE_DIR}:${DF_INFRA_STORAGE_DIR}")

    if local_image:
        infra_service["pull_policy"] = "never"

    save_compose_file(
        {"services": compose, "networks": {docker_network: {"external": True}}},
        directory / "docker-compose.yml",
    )

    echo.info("Pulling docker image(s).")
    run(["docker", "compose", "pull"], directory, quiet=True)
    echo.success(
        "DeepFellow Infra installed.\n"
        "To start the docker image - `deepfellow infra start`.\n"
        "For info about installation - `deepfellow infra info`."
    )
