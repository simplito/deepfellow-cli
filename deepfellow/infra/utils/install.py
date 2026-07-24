# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install infra core logic."""

import random
import string
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from deepfellow.common.config import (
    EnvDict,
    configure_uuid_key,
    read_env_file_to_dict,
    save_env_file,
)
from deepfellow.common.defaults import (
    DF_INFRA_DIRECTORY,
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_IMAGE,
    DF_INFRA_IMAGE_HUB,
    DF_INFRA_NAME,
    DF_INFRA_PORT,
    DF_INFRA_STORAGE_DIR,
    DF_INFRA_URL,
    DOCKER_COMPOSE_CONFIG_FILENAME,
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
from deepfellow.common.exceptions import translate_to_install_error
from deepfellow.common.generate import generate_password
from deepfellow.common.install import assert_docker, ensure_directory
from deepfellow.common.registry import get_newest_image_tag
from deepfellow.common.state import state
from deepfellow.common.system import run
from deepfellow.common.validation import validate_df_name, validate_url


@dataclass
class InstallContext:
    """Read-only values gathered from the environment before any prompting."""

    directory: Path
    docker_socket: str
    newest_image_tag: str | None
    original_env_content: EnvDict  # {} if no prior .env


def inspect(directory: Path, allow_rootful: bool, force_install: bool, image: str, local_image: bool) -> InstallContext:
    """Docker check, directory creation, existing .env read-back.

    No prompts, no network/compose writes.

    Returns:
        InstallContext: Read-only values needed by :func:`resolve`.
    """
    assert_docker()
    docker_socket = get_socket(allow_rootful=allow_rootful)

    # Check if overriding existing installation
    ensure_directory(
        directory, error_message="Unable to create DeepFellow Infra directory.", force_install=force_install
    )
    newest_image_tag = get_newest_image_tag(DF_INFRA_IMAGE_HUB) if not local_image and image == DF_INFRA_IMAGE else None

    # Prepare the starting point for .env
    original_env_content = read_env_file_to_dict(directory / ".env")

    return InstallContext(directory, docker_socket, newest_image_tag, original_env_content)


@dataclass
class InstallConfig:
    """Final, fully-resolved installation values, ready to be persisted."""

    directory: Path
    docker_socket: str
    df_name: str
    infra_url: str
    infra_port: int
    df_infra_image: str
    docker_network: str
    docker_config: Path
    admin_api_key: str
    api_key: str
    mesh_key: str
    compose_prefix: str
    storage_dir: Path
    metrics_username: str
    metrics_password: str
    hugging_face_token: str | None
    civitai_token: str | None
    local_image: bool
    print_keys: bool
    df_connect_to_mesh_url: str | None
    df_connect_to_mesh_key: str | None


def resolve(
    context: InstallContext,
    *,
    port: int,
    image: str,
    docker_config: Path,
    storage: Path,
    hugging_face_token: str | None,
    civitai_token: str | None,
    infra_name: str,
    infra_url: str,
    docker_network: str,
    local_image: bool,
    allow_print_keys: bool | None,
    keep_compose_prefix: bool | None,
    keep_storage: bool | None,
    keep_metrics: bool | None,
) -> InstallConfig:
    """Prompt the user for / apply CLI overrides to the remaining install values.

    Args:
        context: Read-only values gathered by :func:`inspect`.
        port: Published port to serve the DeepFellow Infra from.
        image: DeepFellow Infra docker image, before newest-tag resolution.
        docker_config: Path to the docker config file.
        storage: Storage directory for the DeepFellow Infra services.
        hugging_face_token: Optional Hugging Face token.
        civitai_token: Optional Civitai token.
        infra_name: Requested DF_NAME.
        infra_url: Requested DF_INFRA_URL.
        docker_network: Requested docker network name.
        local_image: Whether a locally built docker image is used.
        allow_print_keys: Whether to print API keys to the console.
        keep_compose_prefix: Whether to keep a previously configured compose prefix.
        keep_storage: Whether to keep a previously configured storage dir.
        keep_metrics: Whether to keep previously configured metrics credentials.

    Returns:
        InstallConfig: The fully-resolved installation configuration.
    """
    original_env_content = context.original_env_content

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

    # Find out which docker network to use
    docker_network = echo.prompt(
        "Provide a docker network name",
        from_args=docker_network,
        original_default=DF_INFRA_DOCKER_NETWORK,
        default=original_env_content.get("df_infra_docker_subnet", docker_network),
    )

    flag_print_keys = echo.confirm("Is it safe to print API keys here?", from_args=allow_print_keys)

    # Collect DF_INFRA_ADMIN_API_KEY
    echo.info("Configuration of DF_INFRA_ADMIN_API_KEY\nkey required for an admin identify in DeepFellow Infra.")
    admin_api_key = configure_uuid_key("DF_INFRA_ADMIN_API_KEY", original_env_content.get("df_infra_admin_api_key"))
    if flag_print_keys:
        echo.info(f"DF_INFRA_ADMIN_API_KEY: {admin_api_key}")

    # Collect DF_INFRA_API_KEY
    echo.info(
        "Configuration of DF_INFRA_API_KEY\nkey needed to communication between DeepFellow Infra and DeepFellow Server."
    )
    api_key = configure_uuid_key("DF_INFRA_API_KEY", original_env_content.get("df_infra_api_key"))
    if flag_print_keys:
        echo.info(f"DF_INFRA_API_KEY: {api_key}")

    # Collect DF_MESH_KEY
    echo.info(
        "Configuration of DF_MESH_KEY\n"
        "key needed by other DeepFellow Infra to attach to this DeepFellow Infra and thus extend the Mesh."
    )
    mesh_key = configure_uuid_key("DF_MESH_KEY", original_env_content.get("df_mesh_key"))
    if flag_print_keys:
        echo.info(f"DF_MESH_KEY: {mesh_key}")

    # Find out the compose prefix
    original_compose_prefix = original_env_content.get("df_infra_compose_prefix")
    if original_compose_prefix is not None and echo.confirm(
        f"Would you like to keep the previously configured compose prefix '{original_compose_prefix}'?",
        from_args=keep_compose_prefix,
        default=True,
    ):
        compose_prefix = str(original_compose_prefix)
    else:
        random_letters = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        compose_prefix = f"df{random_letters}_"

    # Find out the infra storage dir
    original_storage_raw = original_env_content.get("df_infra_storage_dir")
    original_storage: Path | None = Path(str(original_storage_raw)) if original_storage_raw is not None else None
    if (
        original_storage is not None
        and original_storage != DF_INFRA_STORAGE_DIR
        and storage == DF_INFRA_STORAGE_DIR
        and echo.confirm(
            f"Would you like to keep the previously configured storage dir '{original_storage}'?",
            from_args=keep_storage,
            default=True,
        )
    ):
        storage = original_storage

    original_metrics_username = original_env_content.get("df_metrics_username")
    original_metrics_password = original_env_content.get("df_metrics_password")

    if (
        original_metrics_username is not None
        and original_metrics_password is not None
        and echo.confirm(
            "Would you like to keep the previously configured metrics credentials?",
            from_args=keep_metrics,
            default=True,
        )
    ):
        metrics_username = str(original_metrics_username)
        metrics_password = str(original_metrics_password)
    else:
        metrics_username = generate_password(8)
        metrics_password = generate_password(12)

    hugging_face_token = hugging_face_token or echo.prompt(
        "Provide an optional Hugging Face Token",
        from_args=hugging_face_token,
        original_default=None,
        default=original_env_content.get("df_hugging_face_token", hugging_face_token) or "",
        password=True,
    )

    civitai_token = civitai_token or echo.prompt(
        "Provide an optional Civitai Token",
        from_args=civitai_token,
        original_default=None,
        default=original_env_content.get("df_civitai_token", civitai_token) or "",
        password=True,
    )

    return InstallConfig(
        directory=context.directory,
        docker_socket=context.docker_socket,
        df_name=df_name,
        infra_url=df_infra_url,
        infra_port=port,
        df_infra_image=context.newest_image_tag or image,
        docker_network=docker_network,
        docker_config=docker_config,
        admin_api_key=admin_api_key,
        api_key=api_key,
        mesh_key=mesh_key,
        compose_prefix=compose_prefix,
        storage_dir=storage,
        metrics_username=metrics_username,
        metrics_password=metrics_password,
        hugging_face_token=hugging_face_token or None,
        civitai_token=civitai_token or None,
        local_image=local_image,
        print_keys=flag_print_keys,
        df_connect_to_mesh_url=None,
        df_connect_to_mesh_key=None,
    )


def apply(config: InstallConfig) -> None:
    """Create the docker network, write the .env/compose files, and pull the image.

    Purely programmatic: no prompts, so it does not leave a half-configured
    installation behind if an earlier phase (:func:`resolve`) was interrupted.
    """
    config_file = state.cli_config_file
    secrets_file = state.cli_secrets_file

    # Create empty docker config if needed
    if not config.docker_config.is_file():
        config.docker_config.write_text("{}", encoding="utf-8")

    # Create the network if needed
    ensure_network(config.docker_network)

    # Save the envs to the .env file (existing envs are NOT overwritten)
    infra_values: dict[str, str | int] = {
        "DF_NAME": config.df_name,
        "DF_INFRA_URL": config.infra_url,
        "DF_INFRA_PORT": config.infra_port,
        "DF_INFRA_IMAGE": config.df_infra_image,
        "DF_MESH_KEY": config.mesh_key,
        "DF_INFRA_API_KEY": config.api_key,
        "DF_INFRA_ADMIN_API_KEY": config.admin_api_key,
        "DF_CONNECT_TO_MESH_URL": config.df_connect_to_mesh_url or "",
        "DF_CONNECT_TO_MESH_KEY": config.df_connect_to_mesh_key or "",
        "DF_INFRA_DOCKER_SUBNET": config.docker_network,
        "DF_INFRA_COMPOSE_PREFIX": config.compose_prefix,
        "DF_INFRA_DOCKER_CONFIG": str(config.docker_config),
        "DF_INFRA_STORAGE_DIR": config.storage_dir.expanduser().resolve().as_posix(),
        "DF_METRICS_USERNAME": config.metrics_username,
        "DF_METRICS_PASSWORD": config.metrics_password,
    }
    if config.hugging_face_token:
        infra_values["DF_HUGGING_FACE_TOKEN"] = config.hugging_face_token
    if config.civitai_token:
        infra_values["DF_CIVITAI_TOKEN"] = config.civitai_token

    save_env_file(config.directory / ".env", infra_values)
    env_set(config_file, "DF_INFRA_EXTERNAL_URL", f"http://localhost:{config.infra_port}", should_raise=False)
    env_set(secrets_file, "DF_INFRA_ADMIN_API_KEY", config.admin_api_key, should_raise=False)

    # Save the docker compose config
    compose = deepcopy(DOCKER_COMPOSE_INFRA)
    infra_service = compose["infra"]
    add_network_to_service(infra_service, config.docker_network)

    volumes = cast("list", infra_service["volumes"])
    volumes.append(f"{config.docker_socket}:/run/docker.sock")
    volumes.append(f"{config.docker_socket}:/var/run/docker.sock")
    volumes.append("${DF_INFRA_STORAGE_DIR}:${DF_INFRA_STORAGE_DIR}")

    if config.local_image:
        infra_service["pull_policy"] = "never"

    save_compose_file(
        {"services": compose, "networks": {config.docker_network: {"external": True}}},
        config.directory / DOCKER_COMPOSE_CONFIG_FILENAME,
    )

    echo.info("Pulling docker image(s).")
    run(["docker", "compose", "pull"], config.directory, quiet=True)
    echo.success(
        "DeepFellow Infra installed.\n"
        "To start the docker image - `deepfellow infra start`.\n"
        "For info about installation - `deepfellow infra info`."
    )


@translate_to_install_error
def install(
    directory: Path = DF_INFRA_DIRECTORY,
    port: int = DF_INFRA_PORT,
    image: str = DF_INFRA_IMAGE,
    local_image: bool = False,
    docker_config: Path | None = None,
    storage: Path = DF_INFRA_STORAGE_DIR,
    hugging_face_token: str | None = None,
    civitai_token: str | None = None,
    infra_name: str = DF_INFRA_NAME,
    infra_url: str = DF_INFRA_URL,
    docker_network: str = DF_INFRA_DOCKER_NETWORK,
    force_install: bool = False,
    allow_rootful: bool = False,
    allow_print_keys: bool | None = None,
    keep_compose_prefix: bool | None = None,
    keep_storage: bool | None = None,
    keep_metrics: bool | None = None,
) -> None:
    """Install infra with docker."""
    # Retrieve the docker info to fail early in the process in docker is not running or configured differently
    echo.info("Installing DeepFellow Infra.")

    context = inspect(
        directory=directory,
        allow_rootful=allow_rootful,
        force_install=force_install,
        image=image,
        local_image=local_image,
    )

    docker_config = docker_config or directory / "docker-config.json"

    config = resolve(
        context,
        port=port,
        image=image,
        docker_config=docker_config,
        storage=storage,
        hugging_face_token=hugging_face_token,
        civitai_token=civitai_token,
        infra_name=infra_name,
        infra_url=infra_url,
        docker_network=docker_network,
        local_image=local_image,
        allow_print_keys=allow_print_keys,
        keep_compose_prefix=keep_compose_prefix,
        keep_storage=keep_storage,
        keep_metrics=keep_metrics,
    )

    apply(config)
