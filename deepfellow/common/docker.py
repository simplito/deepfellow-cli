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

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from deepfellow.common.echo import echo

DEFAULT_SERVER_ENV_VARS = {
    "DF_SERVER_PORT": "3000",
    "DF_SERVER_API_KEY": "changeme456",
    "DF_DB_PASSWORD": "secret789",
    "DF_SERVER_IMAGE": "private-repo/server:latest",
}

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
            "TEST_INFRA_KEY=${DF_INFRA_API_KEY}",
            "TEST_SERVER_KEY=${DF_SERVER_API_KEY}",
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
        "ports": ["${DF_INFRA_PORT}:8080"],
        "restart": "unless-stopped",
    }
}

COMPOSE_SERVER = {
    "server": {
        "image": "${DF_SERVER_IMAGE}",
        "ports": ["${DF_SERVER_PORT}:3000"],
        "environment": [
            "API_KEY=${DF_SERVER_API_KEY}",
            "DB_PASSWORD=${DF_DB_PASSWORD}",
            "INFRA_URL=http://infra:${DF_INFRA_PORT}",
        ],
        "restart": "unless-stopped",
    }
}


def generate_env_file(env_file: Path, values: Mapping[str, str | int]) -> None:
    """Creates or updates .env file with provided values."""
    # Load existing values if file exists
    existing_vars = {}
    file_existed = env_file.exists()
    if file_existed:
        existing_vars = load_env_file(env_file)

    # Merge existing with new values (new values take precedence)
    final_vars = {**existing_vars, **values}

    content = "# Docker Compose Environment Variables\n# Edit these values as needed\n\n"
    for key, value in final_vars.items():
        content += f"{key}={value}\n"

    env_file.write_text(content)

    action = "Updated" if file_existed else "Generated"
    echo.info(f"{action} {env_file.as_posix()} with environment variables")


def load_env_file(env_file: Path) -> dict[str, str]:
    """Loads .env file and returns dictionary of key-value pairs."""
    env_vars: dict[str, str] = {}
    if not env_file.exists():
        return env_vars

    content = env_file.read_text()
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            if key:  # Only add if key is not empty
                env_vars[key] = value.strip()

    return env_vars


def merge_services(*service_dicts: dict[str, Any]) -> dict[str, Any]:
    """Combines multiple service dictionaries into one."""
    merged: dict[str, Any] = {"services": {}}
    for service_dict in service_dicts:
        merged["services"].update(service_dict)

    return merged


def save_compose_file(services: dict[str, Any], compose_file: Path = Path("docker-compose.yml")) -> None:
    """Saves Docker Compose configuration to YAML file."""
    compose_dict = {"services": services}
    compose_file.write_text(yaml.dump(compose_dict, default_flow_style=False, sort_keys=False))
    echo.info(f"Saved Docker Compose configuration to {compose_file.as_posix()}")


def load_compose_file(compose_file: Path = Path("docker-compose.yml")) -> dict[str, Any]:
    """Loads existing Docker Compose file and returns dictionary."""
    if not compose_file.exists():
        return {"services": {}}

    return yaml.safe_load(compose_file.read_text())
