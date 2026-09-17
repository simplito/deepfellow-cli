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

from deepfellow.server.ssl_on import ssl_on

DIRECTORY = Path("/tmp/deepfellow-infra")


@pytest.fixture
def docker_config() -> dict:
    return {"services": {"server": {"volumes": ["/tmp/deepfellow-infra/data:/data"]}}}


@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_raises_when_only_key_path_provided(mock_assert_docker: Mock) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        ssl_on(directory=DIRECTORY, ssl_key_path="key.pem", ssl_cert_path=None, port=None, server=None)

    assert exc_info.value.exit_code == 1
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_raises_when_only_cert_path_provided(mock_assert_docker: Mock) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        ssl_on(directory=DIRECTORY, ssl_key_path=None, ssl_cert_path="cert.pem", port=None, server=None)

    assert exc_info.value.exit_code == 1
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=False)
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_raises_when_server_not_running(
    mock_assert_docker: Mock, mock_is_service_running: Mock, mock_echo: Mock
) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        ssl_on(directory=DIRECTORY, ssl_key_path=None, ssl_cert_path=None, port=None, server=None)

    assert exc_info.value.exit_code == 1
    assert mock_is_service_running.call_args == mock.call("server", cwd=DIRECTORY)
    assert mock_echo.error.call_count == 1
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_generates_self_signed_cert_when_no_paths_provided(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config

    ssl_on(directory=DIRECTORY, ssl_key_path=None, ssl_cert_path=None, port=None, server=None)

    assert mock_run.call_count == 5
    assert mock_run.call_args_list[1] == mock.call(
        [
            "docker",
            "compose",
            "exec",
            "server",
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:4096",
            "-nodes",
            "-out",
            "/ssl/cert.pem",
            "-keyout",
            "/ssl/key.pem",
            "-days",
            "3650",
            "-subj",
            "/CN=localhost",
        ],
        cwd=DIRECTORY,
        quiet=True,
    )
    assert mock_run.call_args_list[2] == mock.call(
        ["docker", "compose", "cp", "server:/ssl/.", (DIRECTORY / "ssl").as_posix()], cwd=DIRECTORY, quiet=True
    )
    assert mock_echo.success.call_count == 1
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.shutil.copy2")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_copies_provided_cert_files(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy2: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    assert mock_copy2.call_count == 2
    assert mock_copy2.call_args_list[0] == mock.call(Path("my-key.pem"), DIRECTORY / "ssl" / "key.pem")
    assert mock_copy2.call_args_list[1] == mock.call(Path("my-cert.pem"), DIRECTORY / "ssl" / "cert.pem")
    assert mock_run.call_count == 3
    assert mock_echo.success.call_count == 1
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.shutil.copy2")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_raises_when_cert_file_missing(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy2: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    missing_file_error = FileNotFoundError()
    missing_file_error.filename = "missing.pem"
    mock_copy2.side_effect = missing_file_error

    with pytest.raises(typer.Exit) as exc_info:
        ssl_on(directory=DIRECTORY, ssl_key_path="missing.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_args == mock.call("File not found missing.pem")
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.shutil.copy2")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_adds_ssl_volume_when_missing(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy2: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    volumes = docker_config["services"]["server"]["volumes"]
    assert f"{(DIRECTORY / 'ssl').as_posix()}:/ssl" in volumes
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.shutil.copy2")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_skips_ssl_volume_when_already_present(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy2: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    docker_config: dict,
) -> None:
    ssl_volume = f"{(DIRECTORY / 'ssl').as_posix()}:/ssl"
    docker_config["services"]["server"]["volumes"].append(ssl_volume)
    mock_load_compose_file.return_value = docker_config

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    volumes = docker_config["services"]["server"]["volumes"]
    assert volumes.count(ssl_volume) == 1
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.shutil.copy2")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_stores_port_when_provided_and_changed(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy2: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_env_get.side_effect = lambda env_file, key: "8443" if key == "server_port" else None

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=9000, server=None)

    assert mock.call(DIRECTORY / ".env", "server_port", "9000", quiet=True) in mock_env_set.call_args_list
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get")
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.shutil.copy2")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_rewrites_http_url_to_https_when_server_omitted(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy2: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_env_get.side_effect = lambda env_file, key: "http://example.com" if key == "server_url" else None

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    assert mock.call(DIRECTORY / ".env", "server_url", "https://example.com", quiet=True) in mock_env_set.call_args_list
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get")
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.shutil.copy2")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_stores_explicit_server_url_when_provided(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy2: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_env_get.side_effect = lambda env_file, key: "https://old.example.com" if key == "server_url" else None

    ssl_on(
        directory=DIRECTORY,
        ssl_key_path="my-key.pem",
        ssl_cert_path="my-cert.pem",
        port=None,
        server="https://new.example.com",
    )

    assert (
        mock.call(DIRECTORY / ".env", "server_url", "https://new.example.com", quiet=True)
        in mock_env_set.call_args_list
    )
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.shutil.copy2")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_updates_compose_command_and_entrypoint(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy2: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    docker_server = docker_config["services"]["server"]
    assert docker_server["entrypoint"] == []
    assert "--ssl-keyfile /ssl/key.pem --ssl-certfile /ssl/cert.pem" in docker_server["command"]
    assert mock_save_compose_file.call_count == 2
    assert mock_run.call_args_list[-2] == mock.call(["docker", "compose", "down"], cwd=DIRECTORY, quiet=True)
    assert mock_run.call_args_list[-1] == mock.call(
        ["docker", "compose", "up", "--build", "-d", "--remove-orphans"], cwd=DIRECTORY, quiet=True
    )
    assert mock_assert_docker.call_count == 1
