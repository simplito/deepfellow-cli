# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Docker helper methods."""

import os
from pathlib import Path
from typing import Any

import typer
import yaml

from deepfellow.common.config import env_to_dict, read_env_file
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import DockerNetworkError, DockerSocketNotFoundError
from deepfellow.common.system import run


class DockerError(Exception):
    """Raised if any docker command fails."""


def is_docker_installed() -> bool:
    """Checks if docker is installed."""
    try:
        run(["docker", "--version"], capture_output=True, raises=DockerError)
    except (DockerError, FileNotFoundError):
        return False

    return True


def is_user_allowed_to_use_docker() -> bool:
    """Check is user is allowed to use docker."""
    try:
        run(["docker", "ps"], capture_output=True, raises=DockerError)
    except DockerError:
        return False

    return True


def is_user_in_docker_group() -> bool:
    """Check is user is in docker group."""
    groups = run(["groups"], capture_output=True)
    return "docker" in groups if groups is not None else False


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
    result = run(
        ["docker", "context", "inspect", "-f", "{{.Endpoints.docker.Host}}"],
        capture_output=True,
    )
    if result:
        host = result.strip()
        if host.startswith("unix://"):
            return host.replace("unix://", "")

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
    result = run(["docker", "network", "ls", "--format", "{{.Name}}"], capture_output=True)
    if result is None:
        raise DockerNetworkError("Failed to fetch Docker network list")

    networks = result.strip().split("\n")
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
        run(["docker", "network", "create", "--driver", driver, network_name], raises=DockerError)
    except DockerError as exc:
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
        result = run(
            ["docker", "compose", "ps", service, "--status", "running"],
            cwd=cwd,
            raises=DockerError,
            capture_output=True,
        )
    except DockerError:
        return False

    # Running result:
    # NAME            IMAGE                                               ...
    # infra-infra-1   hub.simplito.com/deepfellow/deepfellow-infra:dev   ...

    # Not running result:
    # NAME            IMAGE                                               ...

    return result is not None and len(result.splitlines()) > 1


def get_docker_network(directory: Path) -> str:
    """Get docker network setting."""
    env_file = directory / ".env"
    env_vars = read_env_file(env_file)
    env_content = env_to_dict(env_vars)
    return str(env_content.get("df_infra_docker_subnet", ""))


def parse_docker_compose_ps(data: str) -> dict[str, str]:
    """Parse the output of docker compose ps command.

    Args:
        data: The output string from docker compose ps

    Returns:
        Dictionary with container information keyed by column names
    """
    lines = data.splitlines()

    if len(lines) < 2:
        return {}

    header = lines[0]
    info = lines[1]

    # Find the start positions of each column header
    indexes = {}
    last_end = 0
    headers = header.split()

    for i, header_name in enumerate(headers):
        start = header.find(header_name, last_end)
        if i < len(headers) - 1:
            next_header = headers[i + 1]
            end = header.find(next_header, start)
        else:
            end = len(info)

        indexes[header_name] = (start, end)
        last_end = start + 1

    # Extract data for each column
    result = {}
    for header_name, (start, end) in indexes.items():
        value = info[start:end].strip()
        result[header_name] = value

    return result


def parse_docker_compose_usage(data: str) -> dict[str, str]:
    """Parse the output of docker stats command.

    Args:
        data: The output string from docker stats command

    Returns:
        Dictionary with container usage information
    """
    lines = data.splitlines()

    if len(lines) < 2:
        return {}

    header_line = lines[0]

    # Define the expected column headers in order (as they appear in docker stats)
    column_headers = ["CONTAINER ID", "NAME", "CPU %", "MEM USAGE / LIMIT", "MEM %", "NET I/O", "BLOCK I/O", "PIDS"]

    # Find the start position of each column header
    indexes = {}
    for i, header_name in enumerate(column_headers):
        start = header_line.find(header_name)
        if start == -1:
            continue

        # Determine end position (start of next column or end of line)
        if i < len(column_headers) - 1:
            # Find where the next column starts
            next_start = len(header_line)
            for next_header in column_headers[i + 1 :]:
                next_pos = header_line.find(next_header)
                if next_pos != -1:
                    next_start = next_pos
                    break
            end = next_start
        else:
            end = len(header_line)

        indexes[header_name] = (start, end)

    # Process the first data line (skip header)
    data_line = lines[1]

    container_info = {}
    for header_name, (start, end) in indexes.items():
        # Extract substring respecting column bounds
        value = data_line[start:end].strip() if end <= len(data_line) else data_line[start:].strip()

        # Split MEM USAGE / LIMIT into two separate fields
        if header_name == "MEM USAGE / LIMIT":
            parts = value.split(" / ")
            if len(parts) == 2:
                container_info["MEM USAGE"] = parts[0].strip()
                container_info["MEM LIMIT"] = parts[1].strip()
        else:
            container_info[header_name] = value

    return container_info


def docker_ps(directory: Path, context: str) -> dict[str, str] | None:
    """Run docker compose ps command and display results."""
    # Execute docker compose ps command in the specified directory
    try:
        result = run(["docker", "compose", "ps", context], cwd=directory, capture_output=True)
    except Exception as e:
        echo.debug(e)
        echo.error(f"Failed to get docker status from {context}")
        return None

    # Check if the command returned any containers (header line + at least one data line)
    if not result or len(result.splitlines()) <= 1:
        echo.info(f"No {context} container is currently running.")
        return None

    # Parse the docker ps output into a structured dictionary
    parsed = parse_docker_compose_ps(result)

    # Validate parsing was successful
    if not parsed:
        echo.error("Error parsing docker ps")
        raise typer.Exit(1)

    return parsed


def get_container_id(directory: Path, context: str) -> str:
    """Run docker ps context -q."""
    try:
        result = run(["docker", "compose", "ps", context, "-q"], cwd=directory, capture_output=True)
    except Exception as e:
        echo.debug(e)
        echo.error(f"Failed to check container ID for {context}")
        raise typer.Exit(1) from e

    return str(result)


def docker_stats(directory: Path, context: str) -> dict[str, str] | None:
    """Run docker stats command and display results."""
    container_id = get_container_id(directory, context)
    try:
        result = run(["docker", "stats", container_id, "--no-stream"], cwd=directory, capture_output=True)
    except Exception as e:
        echo.debug(e)
        echo.error(f"Failed to get docker stats for {context}")
        return None

    if not result or len(result.splitlines()) <= 1:
        echo.info(f"No {context} container is currently running.")
        return None

    parsed = parse_docker_compose_usage(result)

    if not parsed:
        echo.error("Error parsing docker response")
        raise typer.Exit(1)

    return parsed


def print_docker_status(directory: Path, context: str) -> None:
    """Collect stats about docker and print them out."""
    ps_response = docker_ps(directory, context) or {}
    stat_response = docker_stats(directory, context) or {}
    response = ps_response | stat_response
    if not response:
        echo.error("Failed to get data from docker.")
        return

    # Display container information in a formatted output
    echo.info(
        f"image: {response.get('IMAGE', 'N/A')}"
        f"\ncreated: {response.get('CREATED', 'N/A')}"
        f"\nstatus: {response.get('STATUS', 'N/A')}"
        f"\nports: {response.get('PORTS', 'N/A')}"
        f"\nCPU: {response.get('CPU %', 'N/A')}"
        f"\nUsed memory: {response.get('MEM USAGE', 'N/A')}"
        f"\nMemory limit: {response.get('MEM LIMIT', 'N/A')}"
        f"\nNET I/O: {response.get('NET I/O', 'N/A')}"
        f"\nDisk I/O: {response.get('BLOCK I/O', 'N/A')}"
    )
