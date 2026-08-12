# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
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
import typer
import yaml

from deepfellow.common.defaults import DOCKER_COMPOSE_CONFIG_FILENAME
from deepfellow.common.docker import (
    DockerError,
    add_network_to_service,
    create_network,
    docker_ps,
    docker_stats,
    ensure_network,
    get_container_id,
    get_docker_network,
    get_socket,
    is_docker_group_available,
    is_docker_installed,
    is_service_running,
    is_user_allowed_to_use_docker,
    is_user_in_docker_group,
    list_networks,
    load_compose_file,
    parse_docker_compose_ps,
    parse_docker_compose_usage,
    print_docker_status,
    remove_volume,
    resolve_compose_volume_name,
    save_compose_file,
    volume_exists,
)
from deepfellow.common.exceptions import DockerNetworkError, DockerSocketNotFoundError


@pytest.fixture
def temp_env_file(tmp_path: Path) -> Path:
    return tmp_path / ".env"


@pytest.fixture
def temp_compose_file(tmp_path: Path) -> Path:
    return tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME


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
    assert DOCKER_COMPOSE_CONFIG_FILENAME in mock_echo.info.call_args[0][0]


def test_load_compose_file_returns_empty_services_when_not_exists() -> None:
    non_existent_file = Path("nonexistent-compose.yaml")

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


def test_parse_docker_compose_ps():
    # Test with sample docker compose ps output
    sample_output = (
        "NAME            IMAGE                                                 COMMAND                  "
        "SERVICE   CREATED       STATUS          PORTS\n"
        'infra-infra-1   hub.simplito.com/deepfellow/deepfellow-infra:0.15.0   "./.venv/bin/uvicorn…"   infra     '
        "2 weeks ago   Up 14 minutes   0.0.0.0:8086->8086/tcp, [::]:8086->8086/tcp"
    )

    result = parse_docker_compose_ps(sample_output)

    assert result["NAME"] == "infra-infra-1"
    assert result["IMAGE"] == "hub.simplito.com/deepfellow/deepfellow-infra:0.15.0"
    assert result["CREATED"] == "2 weeks ago"
    assert result["STATUS"] == "Up 14 minutes"
    assert result["PORTS"] == "0.0.0.0:8086->8086/tcp, [::]:8086->8086/tcp"


def test_parse_docker_compose_ps_empty():
    # Test with empty output
    result = parse_docker_compose_ps("")
    assert result == {}


def test_parse_docker_compose_ps_single_line():
    # Test with only header
    result = parse_docker_compose_ps("NAME            IMAGE")
    assert result == {}


def test_parse_docker_compose_usage():
    # Test with sample docker stats output
    sample_output = (
        "CONTAINER ID   NAME            CPU %     MEM USAGE / LIMIT     MEM %     NET I/O           BLOCK I/O    PIDS\n"
        "9c06fdf7cb59   infra-infra-1   0.21%     53.67MiB / 11.72GiB   0.45%     20.1kB / 5.48kB   353MB / 0B   2"
    )

    result = parse_docker_compose_usage(sample_output)

    assert result["CONTAINER ID"] == "9c06fdf7cb59"
    assert result["NAME"] == "infra-infra-1"
    assert result["CPU %"] == "0.21%"
    assert result["MEM USAGE"] == "53.67MiB"
    assert result["MEM LIMIT"] == "11.72GiB"
    assert result["MEM %"] == "0.45%"
    assert result["NET I/O"] == "20.1kB / 5.48kB"
    assert result["BLOCK I/O"] == "353MB / 0B"
    assert result["PIDS"] == "2"


def test_parse_docker_compose_usage_empty():
    # Test with empty output
    result = parse_docker_compose_usage("")
    assert result == {}


def test_parse_docker_compose_usage_single_line():
    # Test with only header
    sample_output = "CONTAINER ID   NAME            CPU %     MEM USAGE / LIMIT"
    result = parse_docker_compose_usage(sample_output)
    assert result == {}


def test_parse_docker_compose_usage_different_values():
    # Test with different container data
    sample_output = (
        "CONTAINER ID   NAME          CPU %     MEM USAGE / LIMIT    MEM %     NET I/O         BLOCK I/O      PIDS\n"
        "abc123def456   my-app-1      1.50%     128.5MiB / 2GiB      6.27%     1.2MB / 856kB   1.5GB / 10MB   5"
    )

    result = parse_docker_compose_usage(sample_output)

    assert result["CONTAINER ID"] == "abc123def456"
    assert result["NAME"] == "my-app-1"
    assert result["CPU %"] == "1.50%"
    assert result["MEM USAGE"] == "128.5MiB"
    assert result["MEM LIMIT"] == "2GiB"
    assert result["MEM %"] == "6.27%"
    assert result["NET I/O"] == "1.2MB / 856kB"
    assert result["BLOCK I/O"] == "1.5GB / 10MB"
    assert result["PIDS"] == "5"


def test_parse_docker_compose_usage_skips_mem_usage_when_not_split_by_slash() -> None:
    sample_output = "MEM USAGE / LIMIT   PIDS\nno-slash-value-xxx  5"

    result = parse_docker_compose_usage(sample_output)

    assert result == {"PIDS": "5"}


def test_parse_docker_compose_usage_no_trailing_column_found() -> None:
    sample_output = "CONTAINER ID   NAME   CPU %\nabc123def456  app-1  1.2%"

    result = parse_docker_compose_usage(sample_output)

    assert set(result) == {"CONTAINER ID", "NAME", "CPU %"}


@mock.patch("deepfellow.common.docker.run")
def test_is_docker_installed_returns_true_on_success(mock_run: Mock) -> None:
    mock_run.return_value = "Docker version 27.0.0"

    result = is_docker_installed()

    assert result is True


@mock.patch("deepfellow.common.docker.run")
def test_is_user_allowed_to_use_docker_returns_true_on_success(mock_run: Mock) -> None:
    mock_run.return_value = "CONTAINER ID"

    result = is_user_allowed_to_use_docker()

    assert result is True


@mock.patch("deepfellow.common.docker.run")
def test_is_user_allowed_to_use_docker_returns_false_on_docker_error(mock_run: Mock) -> None:
    mock_run.side_effect = DockerError(1, "docker")

    result = is_user_allowed_to_use_docker()

    assert result is False


@pytest.mark.parametrize(
    ("groups_output", "expected"),
    [
        ("user docker sudo", True),
        ("user sudo", False),
        (None, False),
    ],
)
@mock.patch("deepfellow.common.docker.run")
def test_is_user_in_docker_group(mock_run: Mock, groups_output: str | None, expected: bool) -> None:
    mock_run.return_value = groups_output

    result = is_user_in_docker_group()

    assert result is expected


@mock.patch.object(Path, "exists", return_value=False)
def test_is_docker_group_available_returns_false_when_file_missing(mock_exists: Mock) -> None:
    result = is_docker_group_available()

    assert result is False


@mock.patch.object(Path, "read_text", return_value="docker:x:999:someuser\nother:x:1:\n")
@mock.patch.object(Path, "exists", return_value=True)
def test_is_docker_group_available_returns_true_when_group_present(mock_exists: Mock, mock_read_text: Mock) -> None:
    result = is_docker_group_available()

    assert result is True


@mock.patch.object(Path, "read_text", return_value="other:x:1:\n")
@mock.patch.object(Path, "exists", return_value=True)
def test_is_docker_group_available_returns_false_when_group_absent(mock_exists: Mock, mock_read_text: Mock) -> None:
    result = is_docker_group_available()

    assert result is False


def test_get_socket_returns_docker_host_when_unix_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKER_HOST", "unix:///var/run/docker.sock")

    result = get_socket()

    assert result == "/var/run/docker.sock"


@mock.patch("deepfellow.common.docker.run")
def test_get_socket_returns_host_from_docker_context_inspect(mock_run: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    mock_run.return_value = "unix:///run/docker.sock\n"

    result = get_socket()

    assert result == "/run/docker.sock"


@mock.patch.object(Path, "is_file", autospec=True)
@mock.patch("deepfellow.common.docker.run")
def test_get_socket_ignores_non_unix_docker_context_host(
    mock_run: Mock, mock_is_file: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    mock_run.return_value = "tcp://1.2.3.4:2375"
    mock_is_file.return_value = True

    result = get_socket()

    assert result == "/run/user/1000/docker.sock"


@mock.patch.object(Path, "is_file", autospec=True)
@mock.patch("deepfellow.common.docker.run")
def test_get_socket_returns_xdg_runtime_rootless_socket(
    mock_run: Mock, mock_is_file: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    mock_run.return_value = None
    mock_is_file.return_value = True

    result = get_socket()

    assert result == "/run/user/1000/docker.sock"


@mock.patch("deepfellow.common.docker.os.getuid", return_value=1000)
@mock.patch.object(Path, "is_file", autospec=True)
@mock.patch("deepfellow.common.docker.run")
def test_get_socket_falls_back_to_uid_path_when_xdg_socket_missing(
    mock_run: Mock, mock_is_file: Mock, mock_getuid: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/2000")
    mock_run.return_value = None
    mock_is_file.side_effect = lambda self: str(self) == "/run/user/1000/docker.sock"

    result = get_socket()

    assert result == "/run/user/1000/docker.sock"


@mock.patch("deepfellow.common.docker.os.getuid", return_value=1000)
@mock.patch.object(Path, "is_file", autospec=True)
@mock.patch("deepfellow.common.docker.run")
def test_get_socket_returns_uid_rootless_socket_when_no_xdg_runtime_dir(
    mock_run: Mock, mock_is_file: Mock, mock_getuid: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    mock_run.return_value = None
    mock_is_file.return_value = True

    result = get_socket()

    assert result == "/run/user/1000/docker.sock"


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.os.getuid", return_value=1000)
@mock.patch.object(Path, "is_file", autospec=True)
@mock.patch("deepfellow.common.docker.run")
def test_get_socket_returns_rootful_socket_when_allow_rootful(
    mock_run: Mock, mock_is_file: Mock, mock_getuid: Mock, mock_echo: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    mock_run.return_value = None
    mock_is_file.side_effect = lambda self: str(self) == "/run/docker.sock"

    result = get_socket(allow_rootful=True)

    assert result == "/run/docker.sock"
    assert mock_echo.warning.call_count == 1
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.os.getuid", return_value=1000)
@mock.patch.object(Path, "is_file", autospec=True)
@mock.patch("deepfellow.common.docker.run")
def test_get_socket_returns_rootful_socket_when_user_confirms(
    mock_run: Mock, mock_is_file: Mock, mock_getuid: Mock, mock_echo: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    mock_run.return_value = None
    mock_is_file.side_effect = lambda self: str(self) == "/run/docker.sock"
    mock_echo.confirm.return_value = True

    result = get_socket(allow_rootful=False)

    assert result == "/run/docker.sock"
    assert mock_echo.confirm.call_args == mock.call("Do you want to continue?", default=False)


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.os.getuid", return_value=1000)
@mock.patch.object(Path, "is_file", autospec=True)
@mock.patch("deepfellow.common.docker.run")
def test_get_socket_raises_exit_when_rootful_declined(
    mock_run: Mock, mock_is_file: Mock, mock_getuid: Mock, mock_echo: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    mock_run.return_value = None
    mock_is_file.side_effect = lambda self: str(self) == "/run/docker.sock"
    mock_echo.confirm.return_value = False

    with pytest.raises(typer.Exit):
        get_socket(allow_rootful=False)


@mock.patch("deepfellow.common.docker.os.getuid", return_value=1000)
@mock.patch.object(Path, "is_file", autospec=True, return_value=False)
@mock.patch("deepfellow.common.docker.run")
def test_get_socket_raises_docker_socket_not_found_error(
    mock_run: Mock, mock_is_file: Mock, mock_getuid: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    mock_run.return_value = None

    with pytest.raises(DockerSocketNotFoundError):
        get_socket()


@mock.patch("deepfellow.common.docker.run")
def test_list_networks_raises_when_result_none(mock_run: Mock) -> None:
    mock_run.return_value = None

    with pytest.raises(DockerNetworkError):
        list_networks()


@mock.patch("deepfellow.common.docker.run")
def test_list_networks_filters_empty_lines(mock_run: Mock) -> None:
    mock_run.return_value = "bridge\nhost\n\ndeepfellow-infra-net\n"

    result = list_networks()

    assert result == ["bridge", "host", "deepfellow-infra-net"]


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.run")
def test_create_network_calls_run_and_logs_debug(mock_run: Mock, mock_echo: Mock) -> None:
    create_network("deepfellow-net")

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(
        ["docker", "network", "create", "--driver", "bridge", "deepfellow-net"], raises=DockerError, quiet=True
    )
    assert mock_echo.debug.call_count == 1


@mock.patch("deepfellow.common.docker.run")
def test_create_network_raises_docker_network_error_on_failure(mock_run: Mock) -> None:
    mock_run.side_effect = DockerError(1, "docker")

    with pytest.raises(DockerNetworkError):
        create_network("deepfellow-net")


@mock.patch("deepfellow.common.docker.create_network")
@mock.patch("deepfellow.common.docker.list_networks")
def test_ensure_network_creates_network_when_missing(mock_list_networks: Mock, mock_create_network: Mock) -> None:
    mock_list_networks.return_value = []

    ensure_network("deepfellow-net")

    assert mock_create_network.call_count == 1
    assert mock_create_network.call_args == mock.call("deepfellow-net", "bridge")


@mock.patch("deepfellow.common.docker.create_network")
@mock.patch("deepfellow.common.docker.list_networks")
def test_ensure_network_skips_creation_when_present(mock_list_networks: Mock, mock_create_network: Mock) -> None:
    mock_list_networks.return_value = ["deepfellow-net"]

    ensure_network("deepfellow-net")

    assert mock_create_network.call_count == 0


def test_add_network_to_service_creates_networks_list_when_missing() -> None:
    service: dict = {}

    add_network_to_service(service, "deepfellow-net")

    assert service == {"networks": ["deepfellow-net"]}


def test_add_network_to_service_skips_duplicate() -> None:
    service: dict = {"networks": ["deepfellow-net"]}

    add_network_to_service(service, "deepfellow-net")

    assert service == {"networks": ["deepfellow-net"]}


def test_add_network_to_service_appends_when_other_networks_present() -> None:
    service: dict = {"networks": ["other-net"]}

    add_network_to_service(service, "deepfellow-net")

    assert service == {"networks": ["other-net", "deepfellow-net"]}


@mock.patch("deepfellow.common.docker.run")
def test_is_service_running_returns_true_when_running(mock_run: Mock, tmp_path: Path) -> None:
    mock_run.return_value = "NAME            IMAGE\ninfra-infra-1   some-image"

    result = is_service_running("infra", tmp_path)

    assert result is True
    assert mock_run.call_args == mock.call(
        ["docker", "compose", "ps", "infra", "--status", "running"],
        cwd=tmp_path,
        raises=DockerError,
        capture_output=True,
    )


@mock.patch("deepfellow.common.docker.run")
def test_is_service_running_returns_false_when_not_running(mock_run: Mock, tmp_path: Path) -> None:
    mock_run.return_value = "NAME            IMAGE"

    result = is_service_running("infra", tmp_path)

    assert result is False


@mock.patch("deepfellow.common.docker.run")
def test_is_service_running_returns_false_on_docker_error(mock_run: Mock, tmp_path: Path) -> None:
    mock_run.side_effect = DockerError(1, "docker")

    result = is_service_running("infra", tmp_path)

    assert result is False


def test_get_docker_network_returns_subnet_value(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("DF_INFRA_DOCKER_SUBNET=172.20.0.0/16\n")

    result = get_docker_network(tmp_path)

    assert result == "172.20.0.0/16"


def test_get_docker_network_returns_empty_string_when_missing(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("DF_OTHER_VAR=value\n")

    result = get_docker_network(tmp_path)

    assert result == ""


@mock.patch("deepfellow.common.docker.run")
def test_volume_exists_returns_true_on_success(mock_run: Mock) -> None:
    result = volume_exists("server_mongo")

    assert result is True
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(
        ["docker", "volume", "inspect", "server_mongo"], capture_output=True, raises=DockerError
    )


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.run")
def test_volume_exists_returns_false_on_docker_error(mock_run: Mock, mock_echo: Mock) -> None:
    error = DockerError("No such volume: server_mongo")
    mock_run.side_effect = error

    result = volume_exists("server_mongo")

    assert result is False
    assert mock_echo.debug.call_count == 1
    assert mock_echo.debug.call_args == mock.call(error)
    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.common.docker.run")
def test_remove_volume_calls_docker_volume_rm(mock_run: Mock) -> None:
    remove_volume("server_mongo")

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(
        ["docker", "volume", "rm", "server_mongo"], capture_output=True, raises=DockerError
    )


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.run")
def test_remove_volume_raises_docker_error_on_failure(mock_run: Mock, mock_echo: Mock) -> None:
    error = DockerError("volume in use")
    mock_run.side_effect = error

    with pytest.raises(DockerError) as exc_info:
        remove_volume("server_mongo")

    assert exc_info.value is error
    assert mock_echo.debug.call_count == 1
    assert mock_echo.debug.call_args == mock.call(error)


@mock.patch("deepfellow.common.docker.run")
def test_resolve_compose_volume_name_returns_resolved_name(mock_run: Mock, tmp_path: Path) -> None:
    mock_run.return_value = '{"volumes": {"mongo": {"name": "server_mongo"}}}'

    result = resolve_compose_volume_name(tmp_path, "mongo")

    assert result == "server_mongo"
    assert mock_run.call_count == 1
    call_args = mock_run.call_args
    assert call_args.args == (["docker", "compose", "-f", "-", "config", "--format", "json"],)
    assert call_args.kwargs["cwd"] == tmp_path
    assert call_args.kwargs["capture_output"] is True
    assert call_args.kwargs["raises"] is DockerError

    # Assert the two invariants that actually matter (rather than the exact serialized YAML,
    # which is an implementation detail): the volume key is declared, and some service mounts
    # it - Compose drops a volume from its resolved output entirely if no service references it
    # (see commit 8203fd1), so the second invariant is what the synthetic compose file exists to
    # guarantee.
    synthetic_compose = yaml.safe_load(call_args.kwargs["input"])
    assert "mongo" in synthetic_compose.get("volumes", {})
    assert any(
        any(mount.startswith("mongo:") for mount in service.get("volumes", []))
        for service in synthetic_compose.get("services", {}).values()
    )


@mock.patch("deepfellow.common.docker.run")
def test_resolve_compose_volume_name_returns_none_when_key_absent(mock_run: Mock, tmp_path: Path) -> None:
    mock_run.return_value = '{"volumes": {"other": {"name": "server_other"}}}'

    result = resolve_compose_volume_name(tmp_path, "mongo")

    assert result is None


@mock.patch("deepfellow.common.docker.run")
def test_resolve_compose_volume_name_returns_none_on_empty_result(mock_run: Mock, tmp_path: Path) -> None:
    mock_run.return_value = ""

    result = resolve_compose_volume_name(tmp_path, "mongo")

    assert result is None


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.run")
def test_resolve_compose_volume_name_returns_none_on_docker_error(
    mock_run: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    error = DockerError("docker: command not found")
    mock_run.side_effect = error

    result = resolve_compose_volume_name(tmp_path, "mongo")

    assert result is None
    assert mock_echo.debug.call_count == 1
    assert mock_echo.debug.call_args == mock.call(error)
    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.run")
def test_resolve_compose_volume_name_returns_none_on_malformed_json(
    mock_run: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    mock_run.return_value = "not valid json"

    result = resolve_compose_volume_name(tmp_path, "mongo")

    assert result is None
    assert mock_echo.debug.call_count == 1
    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.run")
def test_resolve_compose_volume_name_returns_none_when_volumes_key_is_null(
    mock_run: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    mock_run.return_value = '{"volumes": null}'

    result = resolve_compose_volume_name(tmp_path, "mongo")

    assert result is None
    assert mock_echo.debug.call_count == 0
    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.common.docker.run")
def test_docker_ps_returns_parsed_containers_on_success(mock_run: Mock, tmp_path: Path) -> None:
    mock_run.return_value = (
        "NAME            IMAGE                                                 COMMAND                  "
        "SERVICE   CREATED       STATUS          PORTS\n"
        'infra-infra-1   hub.simplito.com/deepfellow/deepfellow-infra:0.15.0   "./.venv/bin/uvicorn…"   infra     '
        "2 weeks ago   Up 14 minutes   0.0.0.0:8086->8086/tcp, [::]:8086->8086/tcp"
    )

    result = docker_ps(tmp_path, "infra")

    assert result is not None
    assert result["NAME"] == "infra-infra-1"
    assert result["STATUS"] == "Up 14 minutes"


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.run")
def test_docker_ps_returns_none_when_run_raises(mock_run: Mock, mock_echo: Mock, tmp_path: Path) -> None:
    mock_run.side_effect = Exception("boom")

    result = docker_ps(tmp_path, "infra")

    assert result is None
    assert mock_echo.error.call_args == mock.call("Failed to get docker status from infra")


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.run")
def test_docker_ps_returns_none_when_no_containers(mock_run: Mock, mock_echo: Mock, tmp_path: Path) -> None:
    mock_run.return_value = "NAME            IMAGE"

    result = docker_ps(tmp_path, "infra")

    assert result is None
    assert mock_echo.info.call_args == mock.call("No infra container is currently running.")


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.run")
def test_docker_ps_raises_exit_when_parsing_fails(mock_run: Mock, mock_echo: Mock, tmp_path: Path) -> None:
    mock_run.return_value = "\ndata"

    with pytest.raises(typer.Exit):
        docker_ps(tmp_path, "infra")

    assert mock_echo.error.call_args == mock.call("Error parsing docker ps")


@mock.patch("deepfellow.common.docker.run")
def test_get_container_id_returns_result_on_success(mock_run: Mock, tmp_path: Path) -> None:
    mock_run.return_value = "abc123\n"

    result = get_container_id(tmp_path, "infra")

    assert result == "abc123\n"
    assert mock_run.call_args == mock.call(
        ["docker", "compose", "ps", "infra", "-q"], cwd=tmp_path, capture_output=True
    )


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.run")
def test_get_container_id_raises_exit_on_failure(mock_run: Mock, mock_echo: Mock, tmp_path: Path) -> None:
    mock_run.side_effect = Exception("boom")

    with pytest.raises(typer.Exit):
        get_container_id(tmp_path, "infra")

    assert mock_echo.error.call_args == mock.call("Failed to check container ID for infra")


@mock.patch("deepfellow.common.docker.run")
@mock.patch("deepfellow.common.docker.get_container_id")
def test_docker_stats_returns_parsed_stats_on_success(
    mock_get_container_id: Mock, mock_run: Mock, tmp_path: Path
) -> None:
    mock_get_container_id.return_value = "9c06fdf7cb59"
    mock_run.return_value = (
        "CONTAINER ID   NAME            CPU %     MEM USAGE / LIMIT     MEM %     NET I/O           BLOCK I/O    PIDS\n"
        "9c06fdf7cb59   infra-infra-1   0.21%     53.67MiB / 11.72GiB   0.45%     20.1kB / 5.48kB   353MB / 0B   2"
    )

    result = docker_stats(tmp_path, "infra")

    assert result is not None
    assert result["NAME"] == "infra-infra-1"
    assert result["MEM USAGE"] == "53.67MiB"


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.run")
@mock.patch("deepfellow.common.docker.get_container_id")
def test_docker_stats_returns_none_when_run_raises(
    mock_get_container_id: Mock, mock_run: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    mock_get_container_id.return_value = "9c06fdf7cb59"
    mock_run.side_effect = Exception("boom")

    result = docker_stats(tmp_path, "infra")

    assert result is None
    assert mock_echo.error.call_args == mock.call("Failed to get docker stats for infra")


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.run")
@mock.patch("deepfellow.common.docker.get_container_id")
def test_docker_stats_returns_none_when_no_containers(
    mock_get_container_id: Mock, mock_run: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    mock_get_container_id.return_value = "9c06fdf7cb59"
    mock_run.return_value = "CONTAINER ID   NAME"

    result = docker_stats(tmp_path, "infra")

    assert result is None
    assert mock_echo.info.call_args == mock.call("No infra container is currently running.")


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.run")
@mock.patch("deepfellow.common.docker.get_container_id")
def test_docker_stats_raises_exit_when_parsing_fails(
    mock_get_container_id: Mock, mock_run: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    mock_get_container_id.return_value = "9c06fdf7cb59"
    mock_run.return_value = "\ndata"

    with pytest.raises(typer.Exit):
        docker_stats(tmp_path, "infra")

    assert mock_echo.error.call_args == mock.call("Error parsing docker response")


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.docker_stats")
@mock.patch("deepfellow.common.docker.docker_ps")
def test_print_docker_status_logs_error_when_no_data(
    mock_docker_ps: Mock, mock_docker_stats: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    mock_docker_ps.return_value = None
    mock_docker_stats.return_value = None

    print_docker_status(tmp_path, "infra")

    assert mock_echo.error.call_args == mock.call("Failed to get data from docker.")
    assert mock_echo.info.call_count == 0


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.docker_stats")
@mock.patch("deepfellow.common.docker.docker_ps")
def test_print_docker_status_prints_combined_info(
    mock_docker_ps: Mock, mock_docker_stats: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    mock_docker_ps.return_value = {
        "IMAGE": "nginx",
        "CREATED": "2 weeks ago",
        "STATUS": "Up 14 minutes",
        "PORTS": "80:80",
    }
    mock_docker_stats.return_value = {
        "CPU %": "1%",
        "MEM USAGE": "10MiB",
        "MEM LIMIT": "1GiB",
        "NET I/O": "1kB / 1kB",
        "BLOCK I/O": "2kB / 2kB",
    }

    print_docker_status(tmp_path, "infra")

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(
        "image: nginx"
        "\ncreated: 2 weeks ago"
        "\nstatus: Up 14 minutes"
        "\nports: 80:80"
        "\nCPU: 1%"
        "\nUsed memory: 10MiB"
        "\nMemory limit: 1GiB"
        "\nNET I/O: 1kB / 1kB"
        "\nDisk I/O: 2kB / 2kB"
    )
