from collections.abc import Mapping
from pathlib import Path
from unittest import mock

import pytest
import yaml

from deepfellow.common.docker import (
    generate_env_file,
    get_infra_compose,
    get_sample_compose,
    get_server_compose,
    load_compose_file,
    load_env_file,
    merge_services,
    save_compose_file,
)


@pytest.fixture
def temp_env_file(tmp_path: Path) -> Path:
    return tmp_path / ".env"


@pytest.fixture
def temp_compose_file(tmp_path: Path) -> Path:
    return tmp_path / "docker-compose.yml"


@pytest.fixture
def sample_env_vars() -> dict[str, str | int]:
    return {
        "DF_TEST_PORT": 9000,
        "DF_TEST_KEY": "test_secret",
        "DF_TEST_IMAGE": "test:latest",
    }


@pytest.fixture
def existing_env_content() -> str:
    return """# Existing env file
DF_EXISTING_VAR=existing_value
DF_SHARED_VAR=old_value
"""


@mock.patch("deepfellow.common.docker.echo")
def test_generate_env_file_creates_new_file(
    mock_echo: mock.Mock, temp_env_file: Path, sample_env_vars: dict[str, str | int]
) -> None:
    generate_env_file(temp_env_file, sample_env_vars)

    assert temp_env_file.exists()
    content = temp_env_file.read_text()

    assert "# Docker Compose Environment Variables" in content
    assert "DF_TEST_PORT=9000" in content
    assert "DF_TEST_KEY=test_secret" in content
    assert "DF_TEST_IMAGE=test:latest" in content

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(f"Generated {temp_env_file.as_posix()} with environment variables")


@mock.patch("deepfellow.common.docker.echo")
def test_generate_env_file_updates_existing_file(
    mock_echo: mock.Mock,
    temp_env_file: Path,
    existing_env_content: str,
    sample_env_vars: dict[str, str | int],
) -> None:
    temp_env_file.write_text(existing_env_content)

    # Add a shared variable to test precedence
    test_vars = {**sample_env_vars, "DF_SHARED_VAR": "new_value"}

    generate_env_file(temp_env_file, test_vars)

    content = temp_env_file.read_text()

    # Check existing var is preserved
    assert "DF_EXISTING_VAR=existing_value" in content
    # Check new vars are added
    assert "DF_TEST_PORT=9000" in content
    # Check precedence - new value should override old
    assert "DF_SHARED_VAR=new_value" in content
    assert "DF_SHARED_VAR=old_value" not in content

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(f"Updated {temp_env_file.as_posix()} with environment variables")


@mock.patch("builtins.print")
@mock.patch.object(Path, "write_text")
@mock.patch.object(Path, "exists", return_value=False)
def test_generate_env_file_handles_mapping_types(
    mock_exists: mock.Mock, mock_write_text: mock.Mock, mock_print: mock.Mock
) -> None:
    from collections import OrderedDict

    temp_file = Path("test.env")
    ordered_vars: Mapping[str, str | int] = OrderedDict([("DF_A", "first"), ("DF_B", 123)])

    generate_env_file(temp_file, ordered_vars)

    assert mock_write_text.call_count == 1
    content = mock_write_text.call_args[0][0]
    assert "DF_A=first" in content
    assert "DF_B=123" in content


def test_load_env_file_returns_empty_dict_when_file_not_exists() -> None:
    non_existent_file = Path("nonexistent.env")

    result = load_env_file(non_existent_file)

    assert result == {}


def test_load_env_file_parses_env_file_correctly(temp_env_file: Path) -> None:
    content = """# Comment line
DF_PORT=8080
DF_KEY=secret123
DF_MULTI_EQUALS=value=with=equals

# Another comment
DF_SPACES = value with spaces
"""
    temp_env_file.write_text(content)

    result = load_env_file(temp_env_file)

    expected = {
        "DF_PORT": "8080",
        "DF_KEY": "secret123",
        "DF_MULTI_EQUALS": "value=with=equals",
        "DF_SPACES": "value with spaces",
    }
    assert result == expected


def test_load_env_file_ignores_invalid_lines(temp_env_file: Path) -> None:
    content = """# This is a comment
invalid_line_without_equals
=missing_key
DF_VALID=valid_value

    # Indented comment
"""
    temp_env_file.write_text(content)

    result = load_env_file(temp_env_file)

    assert result == {"DF_VALID": "valid_value"}


def test_get_infra_compose_returns_correct_structure() -> None:
    result = get_infra_compose()

    expected = {
        "infra": {
            "image": "${DF_INFRA_IMAGE}",
            "ports": ["${DF_INFRA_PORT}:8080"],
            "environment": [
                "API_KEY=${DF_INFRA_API_KEY}",
            ],
            "restart": "unless-stopped",
        }
    }
    assert result == expected


def test_get_server_compose_returns_correct_structure() -> None:
    result = get_server_compose()

    expected = {
        "server": {
            "image": "${DF_SERVER_IMAGE}",
            "ports": ["${DF_SERVER_PORT}:3000"],
            "environment": [
                "API_KEY=${DF_SERVER_API_KEY}",
                "DB_PASSWORD=${DF_DB_PASSWORD}",
                "INFRA_URL=http://infra:8080",
            ],
            "restart": "unless-stopped",
        }
    }
    assert result == expected


def test_get_sample_compose_returns_test_service() -> None:
    result = get_sample_compose()

    assert "test" in result
    test_service = result["test"]
    assert test_service["image"] == "alpine:latest"
    assert "sh" in test_service["command"]
    assert "TEST_INFRA_KEY=${DF_INFRA_API_KEY}" in test_service["environment"]


def test_merge_services_combines_multiple_services() -> None:
    service1 = {"web": {"image": "nginx"}}
    service2 = {"db": {"image": "postgres"}}
    service3 = {"cache": {"image": "redis"}}

    result = merge_services(service1, service2, service3)

    expected = {
        "services": {
            "web": {"image": "nginx"},
            "db": {"image": "postgres"},
            "cache": {"image": "redis"},
        }
    }
    assert result == expected


def test_merge_services_handles_empty_input() -> None:
    result = merge_services()

    expected = {"services": {}}
    assert result == expected


def test_merge_services_handles_overlapping_services() -> None:
    service1 = {"web": {"image": "nginx:1.0"}}
    service2 = {"web": {"image": "nginx:2.0"}}

    result = merge_services(service1, service2)

    expected = {"services": {"web": {"image": "nginx:2.0"}}}
    assert result == expected


@mock.patch("deepfellow.common.docker.echo")
def test_save_compose_file_writes_yaml_content(mock_echo: mock.Mock, temp_compose_file: Path) -> None:
    services = {"web": {"image": "nginx", "ports": ["80:80"]}}
    expected_compose = {"services": services}

    save_compose_file(services, temp_compose_file)

    assert temp_compose_file.exists()
    content = temp_compose_file.read_text()
    parsed = yaml.safe_load(content)
    assert parsed == expected_compose

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(
        f"Saved Docker Compose configuration to {temp_compose_file.as_posix()}"
    )


@mock.patch("deepfellow.common.docker.echo")
@mock.patch.object(Path, "write_text")
def test_save_compose_file_uses_default_path(mock_write_text: mock.Mock, mock_echo: mock.Mock) -> None:
    services = {}
    expected_compose = {"services": services}

    save_compose_file(services)

    assert mock_write_text.call_count == 1
    yaml_content = mock_write_text.call_args[0][0]
    assert yaml.safe_load(yaml_content) == expected_compose

    assert mock_echo.info.call_count == 1
    assert "docker-compose.yml" in mock_echo.info.call_args[0][0]


def test_load_compose_file_returns_empty_services_when_not_exists() -> None:
    non_existent_file = Path("nonexistent-compose.yml")

    result = load_compose_file(non_existent_file)

    assert result == {"services": {}}


def test_load_compose_file_parses_yaml_correctly(temp_compose_file: Path) -> None:
    compose_content = {
        "version": "3.8",
        "services": {"web": {"image": "nginx", "ports": ["80:80"]}},
    }
    temp_compose_file.write_text(yaml.dump(compose_content))

    result = load_compose_file(temp_compose_file)

    assert result == compose_content


@mock.patch.object(Path, "read_text")
@mock.patch.object(Path, "exists", return_value=True)
def test_load_compose_file_uses_default_path(mock_exists: mock.Mock, mock_read_text: mock.Mock) -> None:
    expected_content = {"services": {"test": {"image": "test"}}}
    mock_read_text.return_value = yaml.dump(expected_content)

    result = load_compose_file()

    assert result == expected_content
