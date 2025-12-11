# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import yaml

from deepfellow.common.docker import (
    DockerError,
    is_docker_installed,
    load_compose_file,
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


@pytest.mark.parametrize("error", [DockerError(1, "docker"), FileNotFoundError()])
@mock.patch("deepfellow.common.docker.run")
def test_is_docker_installed_error(mock_run: Mock, error: Exception) -> None:
    mock_run.side_effect = error

    assert not is_docker_installed()  # Should also be False, not True


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
    expected = {"web": {"image": "nginx", "ports": ["80:80"]}}

    save_compose_file(expected, temp_compose_file)

    assert temp_compose_file.exists()
    content = temp_compose_file.read_text()
    parsed = yaml.safe_load(content)
    assert parsed == expected

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(
        f"Saved Docker Compose configuration to {temp_compose_file.as_posix()}"
    )


@mock.patch("deepfellow.common.docker.echo")
@mock.patch.object(Path, "write_text")
def test_save_compose_file_uses_default_path(mock_write_text: mock.Mock, mock_echo: mock.Mock) -> None:
    expected = {}

    save_compose_file(expected)

    assert mock_write_text.call_count == 1
    yaml_content = mock_write_text.call_args[0][0]
    assert yaml.safe_load(yaml_content) == expected

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


def test_save_compose_file_with_volumes(temp_compose_file: Path):
    compose = {"volumes": {"test_volume_1": None, "test_volume_2": None}}

    save_compose_file(compose, temp_compose_file)

    content = temp_compose_file.read_text()
    assert (
        content
        == """volumes:
  test_volume_1:
  test_volume_2:
"""
    )
