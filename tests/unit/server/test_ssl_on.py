# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.validation import validate_server
from deepfellow.server.ssl_on import ssl_on

DIRECTORY = Path("/tmp/deepfellow-infra")


@pytest.fixture
def docker_config() -> dict:
    return {"services": {"server": {"volumes": ["/tmp/deepfellow-infra/data:/data"]}}}


def _accept_default_url(message: str, validation: Callable[..., Any], default: str | None = None) -> str | None:
    return default


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
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_raises_when_server_not_running(
    mock_assert_docker: Mock, mock_load_install_compose_file: Mock, mock_is_service_running: Mock, mock_echo: Mock
) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        ssl_on(directory=DIRECTORY, ssl_key_path=None, ssl_cert_path=None, port=None, server=None)

    assert exc_info.value.exit_code == 1
    assert mock_is_service_running.call_args == mock.call("server", cwd=DIRECTORY)
    assert mock_echo.error.call_count == 1
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.get_token")
@mock.patch("deepfellow.server.ssl_on.is_service_running")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file", side_effect=typer.Exit(1))
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_raises_before_any_check_when_server_not_installed(
    mock_assert_docker: Mock, mock_load_install_compose_file: Mock, mock_is_service_running: Mock, mock_get_token: Mock
) -> None:
    with pytest.raises(typer.Exit):
        ssl_on(directory=DIRECTORY, ssl_key_path=None, ssl_cert_path=None, port=None, server=None)

    assert mock_load_install_compose_file.call_args == mock.call(DIRECTORY, "server", "Server")
    assert mock_is_service_running.call_count == 0
    assert mock_get_token.call_count == 0


@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_service")
@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
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
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    mock_copy_ssl_files: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_echo.prompt_until_valid.side_effect = _accept_default_url

    ssl_on(directory=DIRECTORY, ssl_key_path=None, ssl_cert_path=None, port=None, server=None)

    assert mock_run.call_count == 4
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
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1,DNS:server",
        ],
        cwd=DIRECTORY,
        quiet=True,
    )
    assert mock_copy_ssl_files.call_args == mock.call("server", DIRECTORY / "ssl", cwd=DIRECTORY)
    assert mock_echo.success.call_count == 1
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_copies_provided_cert_files(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_echo.prompt_until_valid.side_effect = _accept_default_url

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    assert mock_copy_ssl_files_from_paths.call_args == mock.call(
        Path("my-key.pem"), Path("my-cert.pem"), DIRECTORY / "ssl"
    )
    assert mock_run.call_count == 3
    assert mock_echo.success.call_count == 1
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_raises_when_cert_file_missing(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_echo.prompt_until_valid.side_effect = _accept_default_url
    missing_file_error = FileNotFoundError()
    missing_file_error.filename = "missing.pem"
    mock_copy_ssl_files_from_paths.side_effect = missing_file_error

    with pytest.raises(typer.Exit) as exc_info:
        ssl_on(directory=DIRECTORY, ssl_key_path="missing.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_args == mock.call("File not found missing.pem")
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_adds_ssl_volume_when_missing(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_echo.prompt_until_valid.side_effect = _accept_default_url

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    volumes = docker_config["services"]["server"]["volumes"]
    assert f"{(DIRECTORY / 'ssl').as_posix()}:/ssl" in volumes
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_skips_ssl_volume_when_already_present(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    docker_config: dict,
) -> None:
    ssl_volume = f"{(DIRECTORY / 'ssl').as_posix()}:/ssl"
    docker_config["services"]["server"]["volumes"].append(ssl_volume)
    mock_load_compose_file.return_value = docker_config
    mock_echo.prompt_until_valid.side_effect = _accept_default_url

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    volumes = docker_config["services"]["server"]["volumes"]
    assert volumes.count(ssl_volume) == 1
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_stores_port_when_provided_and_changed(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_echo.prompt_until_valid.side_effect = _accept_default_url
    mock_env_get.side_effect = lambda env_file, key, **kwargs: "8443" if key == "server_port" else None

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=9000, server=None)

    assert mock.call(DIRECTORY / ".env", "server_port", "9000", quiet=True) in mock_env_set.call_args_list
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get")
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_rewrites_http_url_to_https_when_server_omitted(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_echo.prompt_until_valid.side_effect = _accept_default_url
    mock_env_get.side_effect = lambda env_file, key, **kwargs: (
        "http://stale.example.com" if key == "server_url" else None
    )
    mock_http_get.return_value = {"server_url": "http://example.com"}

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    assert mock_make_request.call_count == 1
    assert mock_make_request.call_args == mock.call(
        "PUT",
        "http://localhost:8000/admin/config",
        "token",
        data={"server_url": "https://example.com"},
        err_msg="Unable to update server config.",
    )
    assert mock.call(DIRECTORY / ".env", "server_url", "https://example.com", quiet=True) in mock_env_set.call_args_list
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get")
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_stores_explicit_server_url_when_provided(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_env_get.side_effect = lambda env_file, key, **kwargs: (
        "https://old.example.com" if key == "server_url" else None
    )

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
    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_enables_tls_through_uvicorn_env_and_restarts(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_echo.prompt_until_valid.side_effect = _accept_default_url

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    docker_server = docker_config["services"]["server"]
    assert "command" not in docker_server
    assert "entrypoint" not in docker_server
    assert docker_server["environment"] == ["UVICORN_SSL_KEYFILE=/ssl/key.pem", "UVICORN_SSL_CERTFILE=/ssl/cert.pem"]
    assert mock_save_compose_file.call_count == 2
    assert mock_run.call_args_list[-2] == mock.call(["docker", "compose", "down"], cwd=DIRECTORY, quiet=True)
    assert mock_run.call_args_list[-1] == mock.call(
        ["docker", "compose", "up", "--build", "-d", "--remove-orphans"], cwd=DIRECTORY, quiet=True
    )
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "https://example.com"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get")
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_skips_url_writes_when_already_https(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_echo.prompt_until_valid.side_effect = _accept_default_url
    mock_env_get.side_effect = lambda env_file, key, **kwargs: "https://example.com" if key == "server_url" else None

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    assert mock_make_request.call_count == 0
    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8443"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get")
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_talks_to_admin_api_on_port_before_change(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_echo.prompt_until_valid.side_effect = _accept_default_url
    mock_env_get.side_effect = lambda env_file, key, **kwargs: "8443" if key == "server_port" else None

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=9000, server=None)

    assert mock_get_token.call_args == mock.call(mock.ANY, "http://localhost:8443")
    assert mock_http_get.call_args == mock.call(
        "http://localhost:8443/admin/config", "token", item_name="Server config"
    )
    assert mock_make_request.call_args.args[:2] == ("PUT", "http://localhost:8443/admin/config")


@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_asks_for_url_with_https_default_when_server_omitted(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_echo.prompt_until_valid.return_value = "https://df.example.com"

    ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    assert mock_echo.prompt_until_valid.call_args == mock.call(
        "Public https URL of DeepFellow Server", validate_server, default="https://localhost:8000"
    )
    assert mock_make_request.call_args.kwargs["data"] == {"server_url": "https://df.example.com"}
    assert mock.call(DIRECTORY / ".env", "server_url", "https://df.example.com", quiet=True) in (
        mock_env_set.call_args_list
    )


@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_leaves_install_untouched_when_url_prompt_aborted(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config
    mock_echo.prompt_until_valid.side_effect = typer.Exit(1)

    with pytest.raises(typer.Exit):
        ssl_on(directory=DIRECTORY, ssl_key_path="my-key.pem", ssl_cert_path="my-cert.pem", port=None, server=None)

    assert mock_save_compose_file.call_count == 0
    assert mock_copy_ssl_files_from_paths.call_count == 0
    assert mock_run.call_count == 0
    assert mock_make_request.call_count == 0


@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_warns_when_url_host_is_docker_service_name(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config

    ssl_on(
        directory=DIRECTORY,
        ssl_key_path="my-key.pem",
        ssl_cert_path="my-cert.pem",
        port=None,
        server="https://server:8000",
    )

    assert mock_echo.warning.call_count == 1
    assert '"server" in https://server:8000 resolves only inside Docker' in mock_echo.warning.call_args.args[0]


@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_does_not_warn_when_url_host_is_public(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config

    ssl_on(
        directory=DIRECTORY,
        ssl_key_path="my-key.pem",
        ssl_cert_path="my-cert.pem",
        port=None,
        server="https://df.example.com",
    )

    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_service")
@mock.patch("deepfellow.server.ssl_on.make_request")
@mock.patch("deepfellow.server.ssl_on.http_get", return_value={"server_url": "http://localhost:8000"})
@mock.patch("deepfellow.server.ssl_on.get_token", return_value="token")
@mock.patch("deepfellow.server.ssl_on.echo")
@mock.patch("deepfellow.server.ssl_on.run")
@mock.patch("deepfellow.server.ssl_on.env_set")
@mock.patch("deepfellow.server.ssl_on.env_get", return_value=None)
@mock.patch("deepfellow.server.ssl_on.save_compose_file")
@mock.patch("deepfellow.server.ssl_on.load_install_compose_file")
@mock.patch("deepfellow.server.ssl_on.is_service_running", return_value=True)
@mock.patch("deepfellow.server.ssl_on.copy_ssl_files_from_paths")
@mock.patch("deepfellow.server.ssl_on.Path.mkdir")
@mock.patch("deepfellow.server.ssl_on.assert_docker")
def test_ssl_on_names_self_signed_cert_after_url(
    mock_assert_docker: Mock,
    mock_mkdir: Mock,
    mock_copy_ssl_files_from_paths: Mock,
    mock_is_service_running: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_make_request: Mock,
    mock_copy_ssl_files: Mock,
    docker_config: dict,
) -> None:
    mock_load_compose_file.return_value = docker_config

    ssl_on(directory=DIRECTORY, ssl_key_path=None, ssl_cert_path=None, port=None, server="https://df.example.com")

    openssl_args = mock_run.call_args_list[1].args[0]
    assert openssl_args[-4:] == [
        "-subj",
        "/CN=df.example.com",
        "-addext",
        "subjectAltName=DNS:localhost,IP:127.0.0.1,DNS:server,DNS:df.example.com",
    ]
