# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Docker Compose Editor.

A lightweight tool for generating Docker Compose configurations with environment variable support.
Uses .env files with DF_ prefixed variables that are automatically substituted by Docker Compose.

Sample usage:
    # Generate separate .env files for infra and server
    generate_env_file(Path("infra/.env"), DEFAULT_INFRA_ENV_VARS)
    generate_env_file(Path("server/.env"), DEFAULT_SERVER_ENV_VARS)

    # Create separate compose files
    infra_compose = merge_services(get_infra_compose())
    save_compose_file(infra_compose, Path("infra/docker-compose.yml"))

    server_compose = merge_services(get_server_compose())
    save_compose_file(server_compose, Path("server/docker-compose.yml"))

    # Or create combined compose with all env vars
    generate_env_file(Path(".env"), DEFAULT_ENV_VARS)
    full_compose = merge_services(get_infra_compose(), get_server_compose())
    save_compose_file(full_compose)

    # Create test compose to verify environment variables
    test_compose = merge_services(get_sample_compose())
    save_compose_file(test_compose, Path("docker-compose.test.yml"))
"""

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import DockerNetworkError, DockerSocketNotFoundError
from deepfellow.common.system import run


def is_docker_installed() -> bool:
    """Checks if docker is installed."""
    try:
        subprocess.run(["docker --version"], shell=True, check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

    return True


def is_user_allowed_to_use_docker() -> bool:
    """Check is user is allowed to use docker."""
    try:
        subprocess.run("docker ps", shell=True, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        return False

    return True


def is_user_in_docker_group() -> bool:
    """Check is user is in docker group."""
    groups = subprocess.run(["groups"], shell=True, check=True, capture_output=True, text=True)
    return "docker" in groups.stdout


def is_docker_group_available() -> bool:
    """Check if group docker is present in the system."""
    group_file = Path("/etc/group")
    if not group_file.exists():
        return False

    return any(line.startswith("docker:") for line in group_file.read_text().splitlines())


def merge_services(*service_dicts: dict[str, Any]) -> dict[str, Any]:
    """Combines multiple service dictionaries into one."""
    merged: dict[str, Any] = {"services": {}}
    for service_dict in service_dicts:
        merged["services"].update(service_dict)

    return merged


def represent_none(self: yaml.representer.BaseRepresenter, _: None) -> yaml.ScalarNode:
    """Custom representer for None values.

    Required for volumes to generate:

    volumes:
      milvus:
      etcd:
    """
    return self.represent_scalar("tag:yaml.org,2002:null", "")


yaml.add_representer(type(None), represent_none)


class DockerError(Exception):
    """Raised if any docker command fails."""


def save_compose_file(
    compose_dict: dict[str, Any],
    compose_file: Path = Path("docker-compose.yml"),
    quiet: bool = False,
    file_info: str = "Docker Compose configuration",
) -> None:
    """Saves Docker Compose configuration to YAML file."""
    compose_file.write_text(yaml.dump(compose_dict, default_flow_style=False, sort_keys=False, width=1000))
    msg = echo.debug if quiet else echo.info
    msg(f"Saved {file_info} to {compose_file.as_posix()}")


def load_compose_file(compose_file: Path = Path("docker-compose.yml")) -> dict[str, Any]:
    """Loads existing Docker Compose file and returns dictionary."""
    if not compose_file.exists():
        return {"services": {}}

    return yaml.safe_load(compose_file.read_text())


def get_socket() -> str:
    """Get the Docker socket.

    Detect active docker socket with `docker context inspect`
    https://docs.docker.com/reference/cli/docker/context/inspect/

    Returns:
        str: the path to the socket

    Raises:
        DockerNetworkError: When unable to find the socket
    """
    if (docker_host := os.getenv("DOCKER_HOST")) and docker_host.startswith("unix://"):
        return docker_host.replace("unix://", "")

    # Try to find the active docker socket
    try:
        result = subprocess.run(
            ["docker", "context", "inspect", "-f", "{{.Endpoints.docker.Host}}"], capture_output=True, text=True
        )
        if result.returncode == 0:
            host = result.stdout.strip()
            if host.startswith("unix://"):
                return host.replace("unix://", "")

    except subprocess.CalledProcessError:
        pass

    socket_file = "docker.sock"

    # Let's see if the rootless socket exists
    rootless_path: str | None = None
    if xdg_runtime_dir := os.getenv("XDG_RUNTIME_DIR"):
        rootless_path = f"{xdg_runtime_dir}/{socket_file}"
        if Path(rootless_path).is_file():
            return rootless_path

    uid = os.getuid()
    rootless_path = f"/run/user/{uid}/{socket_file}"
    if Path(rootless_path).is_file():
        return rootless_path

    # Let's try with rootfull
    rootful_path = f"/run/{socket_file}"
    if Path(rootful_path).is_file():
        return rootful_path

    raise DockerSocketNotFoundError()


def list_networks() -> list[str]:
    """Returns a list of all Docker network names.

    https://docs.docker.com/reference/cli/docker/network/ls#format

    Returns:
        list[str]: List of network names
        ['bridge', 'host', 'deepfellow-infra-net']

    Raises:
        DockerNetworkError: When unable to fetch network list
    """
    try:
        result = subprocess.run(
            ["docker", "network", "ls", "--format", "{{.Name}}"], capture_output=True, text=True, check=True
        )
        networks = result.stdout.strip().split("\n")
    except subprocess.CalledProcessError as exc:
        raise DockerNetworkError("Failed to fetch Docker network list") from exc

    # Filter potential empty lines
    return [net for net in networks if net]


def create_network(network_name: str, driver: str = "bridge") -> None:
    """Creates a new Docker network.

    https://docs.docker.com/reference/cli/docker/network/create

    Args:
        network_name: Name of the network to create
        driver: Network driver (default: 'bridge')

    Returns:
        bool: True if network was created, False on error

    Raises:
        DockerNetworkError: When unable to create network
    """
    try:
        subprocess.run(
            ["docker", "network", "create", "--driver", driver, network_name],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise DockerNetworkError(f"Failed to create network '{network_name}'") from exc


def ensure_network(network_name: str, driver: str = "bridge") -> None:
    """Ensures a Docker network exists. Creates it if it doesn't exist.

    Args:
        network_name: Name of the network
        driver: Network driver (default: 'bridge')

    Returns:
        bool: True if network exists or was created

    Raises:
        DockerNetworkError: When unable to list or create network
    """
    networks = list_networks()
    if network_name not in networks:
        create_network(network_name, driver)


def add_network_to_service(service: dict, network_name: str) -> None:
    """Add a Docker network to a docker service's \"networks\" field.

    Args:
        service: Dictionary containing service configuration
        network_name: Name of the network

    Returns:
        None
    """
    service["networks"] = service.get("networks", [network_name])
    if network_name not in service["networks"]:
        service["networks"].append(network_name)


def is_service_running(service: str, cwd: Path) -> bool:
    """Check if service is running."""
    result: str | None = None
    try:
        result = run(f"docker compose ps {service} --status running", cwd=cwd, raises=DockerError, capture_output=True)
    except DockerError:
        return False

    # Running result:
    # NAME            IMAGE                                               ...
    # infra-infra-1   hub.simplito.com/deepfellow/deepfellow-infra:dev   ...

    # Not running result:
    # NAME            IMAGE                                               ...

    return result is not None and len(result.splitlines()) > 1
