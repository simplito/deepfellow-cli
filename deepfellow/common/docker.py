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

COMPOSE_SAMPLE = {
    "test": {
        "image": "alpine:latest",
        "command": [
            "sh",
            "-c",
            "echo 'Environment Variables from .env file:' "
            "&& echo 'TEST_ variables:' && env | grep '^TEST_' | sort "
            "&& echo 'DF_ variables:' && env | grep '^DF_' | sort "
            "&& echo 'Test completed' && sleep 10",
        ],
        "environment": [
            "TEST_DF_INFRA_API_KEY=${DF_INFRA_API_KEY}",
            "TEST_DF_INFRA_URL=${DF_INFRA_URL}",
            "TEST_INFRA_PORT=${DF_INFRA_PORT}",
            "TEST_SERVER_PORT=${DF_SERVER_PORT}",
            "TEST_DB_PASSWORD=${DF_DB_PASSWORD}",
            "TEST_INFRA_IMAGE=${DF_INFRA_IMAGE}",
            "TEST_SERVER_IMAGE=${DF_SERVER_IMAGE}",
        ],
    }
}

COMPOSE_INFRA = {
    "infra": {
        "image": "${DF_INFRA_IMAGE}",
        "ports": ["${DF_INFRA_PORT}:8086"],
        "environment": [
            "DF_NAME=${DF_NAME}",
            "DF_INFRA_ADMIN_API_KEY=${DF_INFRA_ADMIN_API_KEY}",
            "DF_INFRA_API_KEY=${DF_INFRA_API_KEY}",
            "DF_INFRA_URL=${DF_INFRA_URL}",
            "DF_MESH_KEY=${DF_MESH_KEY}",
            "DF_CONNECT_TO_MESH_URL=${DF_CONNECT_TO_MESH_URL}",
            "DF_CONNECT_TO_MESH_KEY=${DF_CONNECT_TO_MESH_KEY}",
            "DF_DOCKER_SUBNET=${DF_INFRA_DOCKER_SUBNET}",
            "DF_COMPOSE_PREFIX=${DF_INFRA_COMPOSE_PREFIX}",
            "DF_HUGGING_FACE_API_KEY=${DF_HUGGING_FACE_API_KEY}",
            "DF_CIVITAI_TOKEN=${DF_CIVITAI_TOKEN}",
        ],
        "restart": "unless-stopped",
        "volumes": [
            "${DF_INFRA_DOCKER_CONFIG}:/root/.docker/config.json:ro",
        ],
    },
}

COMPOSE_SERVER = {
    "server": {
        "container_name": "server",
        "image": "${DF_SERVER_IMAGE}",
        "ports": ["${DF_SERVER_PORT}:8000"],
        "environment": [
            "DF_MONGO_URL=${DF_MONGO_URL}",
            "DF_MONGO_USER=${DF_MONGO_USER}",
            "DF_MONGO_PASSWORD=${DF_MONGO_PASSWORD}",
            "DF_MONGO_DB=${DF_MONGO_DB}",
            "DF_VECTOR_DATABASE__PROVIDER__ACTIVE=${DF_VECTOR_DATABASE__PROVIDER__ACTIVE}",
            "DF_VECTOR_DATABASE__PROVIDER__TYPE=${DF_VECTOR_DATABASE__PROVIDER__TYPE}",
            "DF_VECTOR_DATABASE__PROVIDER__URL=${DF_VECTOR_DATABASE__PROVIDER__URL}",
            "DF_VECTOR_DATABASE__PROVIDER__DB=${DF_VECTOR_DATABASE__PROVIDER__DB}",
            "DF_VECTOR_DATABASE__PROVIDER__USER=${DF_VECTOR_DATABASE__PROVIDER__USER}",
            "DF_VECTOR_DATABASE__PROVIDER__PASSWORD=${DF_VECTOR_DATABASE__PROVIDER__PASSWORD}",
            "DF_VECTOR_DATABASE__EMBEDDING__ACTIVE=${DF_VECTOR_DATABASE__EMBEDDING__ACTIVE}",
            "DF_VECTOR_DATABASE__EMBEDDING__ENDPOINT=${DF_VECTOR_DATABASE__EMBEDDING__ENDPOINT}",
            "DF_VECTOR_DATABASE__EMBEDDING__MODEL=${DF_VECTOR_DATABASE__EMBEDDING__MODEL}",
            "DF_VECTOR_DATABASE__EMBEDDING__SIZE=${DF_VECTOR_DATABASE__EMBEDDING__SIZE}",
        ],
        "restart": "unless-stopped",
        "healthcheck": {
            "test": "curl -f http://localhost:${DF_SERVER_PORT}/docs || exit 1",
            "interval": "5m",
            "timeout": "2s",
            "retries": 3,
        },
    }
}

COMPOSE_VECTOR_DB = {
    "etcd": {
        "container_name": "etcd",
        "image": "quay.io/coreos/etcd:v3.5.18",
        "environment": [
            "ETCD_AUTO_COMPACTION_MODE=revision",
            "ETCD_AUTO_COMPACTION_RETENTION=1000",
            "ETCD_QUOTA_BACKEND_BYTES=4294967296",
            "ETCD_SNAPSHOT_COUNT=50000",
        ],
        "ports": ["2379:2379"],
        "volumes": ["etcd:/etcd"],
        "command": (
            "etcd -advertise-client-urls=http://etcd:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd"
        ),
        "healthcheck": {
            "test": ["CMD", "etcdctl", "endpoint", "health"],
            "interval": "30s",
            "timeout": "20s",
            "retries": 3,
        },
    },
    "minio": {
        "container_name": "minio",
        "image": "minio/minio:RELEASE.2024-12-18T13-15-44Z",
        "environment": [
            "MINIO_ACCESS_KEY=minioadmin",
            "MINIO_SECRET_KEY=minioadmin",
        ],
        "ports": ["9001:9001", "9000:9000"],
        "volumes": ["minio:/minio_data"],
        "command": 'minio server /minio_data --console-address ":9001"',
        "healthcheck": {
            "test": "curl -f http://localhost:9000/minio/health/live",
            "interval": "30s",
            "timeout": "20s",
            "retries": 3,
        },
    },
    "milvus": {
        "container_name": "milvus",
        "image": "milvusdb/milvus:v2.6.2",
        "command": "milvus run standalone",
        "security_opt": ["seccomp:unconfined"],
        "environment": [
            "ETCD_ENDPOINTS=etcd:2379",
            "MINIO_ADDRESS=minio:9000",
            "MQ_TYPE=woodpecker",
        ],
        "volumes": ["milvus:/var/lib/milvus"],
        "healthcheck": {
            "test": "curl -f http://localhost:9091/healthz",
            "interval": "30s",
            "start_period": "90s",
            "timeout": "20s",
            "retries": 3,
        },
        "ports": ["19530:19530", "9091:9091"],
        "depends_on": ["etcd", "minio"],
    },
}

COMPOSE_MONGO_DB = {
    "mongo": {
        "container_name": "mongo",
        "image": "mongo:8",
        "restart": "always",
        "expose": ["27017"],
        "ports": ["27017:27017"],
        "volumes": ["mongo:/data/db"],
        "environment": [
            "MONGO_INITDB_ROOT_USERNAME=${DF_MONGO_USER}",
            "MONGO_INITDB_ROOT_PASSWORD=${DF_MONGO_PASSWORD}",
        ],
        "healthcheck": {
            "test": "mongosh --eval 'db.runCommand(\"ping\")'",
            "interval": "10s",
            "timeout": "10s",
            "retries": 5,
            "start_period": "5s",
        },
    }
}


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


def save_compose_file(compose_dict: dict[str, Any], compose_file: Path = Path("docker-compose.yml")) -> None:
    """Saves Docker Compose configuration to YAML file."""
    compose_file.write_text(yaml.dump(compose_dict, default_flow_style=False, sort_keys=False))
    echo.info(f"Saved Docker Compose configuration to {compose_file.as_posix()}")


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


def find_docker_config(explicit_path: Path | None = None) -> Path:
    """Finds Docker config.json file.

    Search order:
    1. Explicit path from --docker-config (if provided)
    2. ~/.docker/config.json (rootless/user)
    3. /root/.docker/config.json (rootful)

    Args:
        explicit_path: Optional explicit path to config.json from CLI argument

    Returns:
        Path: Path to the config.json file

    Raises:
        FileNotFoundError: If config.json cannot be found in any location
    """
    if explicit_path is not None:
        explicit = explicit_path.expanduser().resolve()
        if explicit.exists() and explicit.is_file():
            return explicit

        raise FileNotFoundError(f"Explicitly specified Docker config not found: {explicit_path}")

    user_config = Path.home() / ".docker" / "config.json"
    if user_config.exists() and user_config.is_file():
        return user_config

    root_config = Path("/root/.docker/config.json")
    if root_config.exists() and root_config.is_file():
        return root_config

    raise FileNotFoundError("Docker config.json not found.")
