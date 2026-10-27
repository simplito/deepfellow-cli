# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
import typer

from deepfellow.common.validation import validate_server
from deepfellow.infra.ssl_on import ssl_on


@pytest.fixture
def compose_data() -> dict:
    return {"services": {"infra": {"volumes": []}}}


@pytest.fixture
def default_ssl_kwargs(tmp_path: Path) -> dict:
    return {
        "directory": tmp_path,
        "ssl_key_path": "",
        "ssl_cert_path": "",
        "port": None,
        "server": None,
    }


def _accept_default_url(message: str, validation: Callable[..., Any], default: str | None = None) -> str | None:
    return default


@pytest.fixture
def mocks():
    with (
        mock.patch("deepfellow.infra.ssl_on.copy_ssl_files_from_paths") as m_copy_ssl_files_from_paths,
        mock.patch("deepfellow.infra.ssl_on.run") as m_run,
        mock.patch("deepfellow.infra.ssl_on.copy_ssl_files_from_service") as m_copy_ssl_files,
        mock.patch("deepfellow.infra.ssl_on.env_set") as m_env_set,
        mock.patch("deepfellow.infra.ssl_on.env_get") as m_env_get,
        mock.patch("deepfellow.infra.ssl_on.save_compose_file") as m_save,
        mock.patch("deepfellow.infra.ssl_on.load_install_compose_file") as m_load,
        mock.patch("deepfellow.infra.ssl_on.is_service_running") as m_is_running,
        mock.patch("deepfellow.infra.ssl_on.echo") as m_echo,
        mock.patch("deepfellow.infra.ssl_on.assert_docker") as m_assert_docker,
        mock.patch("deepfellow.infra.ssl_on.check_infra_directory") as m_check,
        mock.patch("deepfellow.infra.ssl_on.infra_admin_request", return_value={"entries": []}) as m_admin_request,
    ):
        m_echo.prompt_until_valid.side_effect = _accept_default_url
        yield SimpleNamespace(
            copy_ssl_files_from_paths=m_copy_ssl_files_from_paths,
            run=m_run,
            copy_ssl_files=m_copy_ssl_files,
            env_set=m_env_set,
            env_get=m_env_get,
            save=m_save,
            load=m_load,
            is_running=m_is_running,
            echo=m_echo,
            assert_docker=m_assert_docker,
            check=m_check,
            admin_request=m_admin_request,
        )


def test_ssl_on_calls_check_infra_directory(
    mocks: SimpleNamespace, tmp_path: Path, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**default_ssl_kwargs)

    assert mocks.check.call_count == 1
    assert mocks.check.call_args == ((tmp_path,), {})
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_errors_when_only_key_provided(mocks: SimpleNamespace, tmp_path: Path):
    with pytest.raises(typer.Exit):
        ssl_on(directory=tmp_path, ssl_key_path="/key.pem", ssl_cert_path="", port=None, server=None)

    assert mocks.echo.error.call_count == 1
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_errors_when_only_cert_provided(mocks: SimpleNamespace, tmp_path: Path):
    with pytest.raises(typer.Exit):
        ssl_on(directory=tmp_path, ssl_key_path="", ssl_cert_path="/cert.pem", port=None, server=None)

    assert mocks.echo.error.call_count == 1
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_errors_before_any_check_when_infra_not_installed(
    mocks: SimpleNamespace, tmp_path: Path, default_ssl_kwargs: dict
):
    mocks.load.side_effect = typer.Exit(1)

    with pytest.raises(typer.Exit):
        ssl_on(**default_ssl_kwargs)

    assert mocks.load.call_args == mock.call(tmp_path, "infra", "Infra")
    assert mocks.is_running.call_count == 0
    assert mocks.admin_request.call_count == 0
    assert mocks.echo.prompt_until_valid.call_count == 0


def test_ssl_on_errors_when_infra_not_running(mocks: SimpleNamespace, tmp_path: Path):
    mocks.is_running.return_value = False
    with pytest.raises(typer.Exit):
        ssl_on(directory=tmp_path, ssl_key_path="", ssl_cert_path="", port=None, server=None)

    assert mocks.echo.error.call_count == 1
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_adds_ssl_volume_when_not_present(
    mocks: SimpleNamespace, tmp_path: Path, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**default_ssl_kwargs)

    ssl_dir_str = (tmp_path / "ssl").as_posix()

    assert f"{ssl_dir_str}:/ssl" in compose_data["services"]["infra"]["volumes"]
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_does_not_add_volume_when_already_present(
    mocks: SimpleNamespace, tmp_path: Path, default_ssl_kwargs: dict
):
    ssl_dir_str = (tmp_path / "ssl").as_posix()
    compose = {"services": {"infra": {"volumes": [f"{ssl_dir_str}:/ssl"]}}}
    mocks.is_running.return_value = True
    mocks.load.return_value = compose
    mocks.env_get.return_value = None

    ssl_on(**default_ssl_kwargs)

    assert len(compose["services"]["infra"]["volumes"]) == 1
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_saves_compose_twice(
    mocks: SimpleNamespace, tmp_path: Path, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**default_ssl_kwargs)

    assert mocks.save.call_count == 2
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_runs_mkdir_in_container(
    mocks: SimpleNamespace, tmp_path: Path, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**default_ssl_kwargs)

    assert (
        mock.call(["docker", "compose", "exec", "infra", "mkdir", "/ssl", "-p"], cwd=tmp_path)
        in mocks.run.call_args_list
    )
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_copies_cert_files_when_paths_provided(
    mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**{**default_ssl_kwargs, "ssl_key_path": "/key.pem", "ssl_cert_path": "/cert.pem"})

    assert mocks.copy_ssl_files_from_paths.call_args == mock.call(
        Path("/key.pem"), Path("/cert.pem"), default_ssl_kwargs["directory"] / "ssl"
    )
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_errors_when_cert_file_not_found(mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict):
    mocks.copy_ssl_files_from_paths.side_effect = FileNotFoundError(2, "No such file", "/key.pem")
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    with pytest.raises(typer.Exit):
        ssl_on(**{**default_ssl_kwargs, "ssl_key_path": "/key.pem", "ssl_cert_path": "/cert.pem"})

    assert mocks.echo.error.call_args == mock.call("File not found /key.pem")
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_runs_openssl_when_no_paths_provided(
    mocks: SimpleNamespace, tmp_path: Path, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**default_ssl_kwargs)

    assert any("openssl" in str(arg) for arg in mocks.run.call_args_list)
    assert mocks.copy_ssl_files.call_args == mock.call("infra", tmp_path / "ssl", cwd=tmp_path)
    assert mocks.assert_docker.call_count == 1


def _env_values(values: dict[str, str]) -> Callable[..., str | None]:
    return lambda env_file, key, **kwargs: values.get(key, kwargs.get("default"))


def _config_with_infra_url(infra_url: str) -> dict[str, Any]:
    return {"entries": [{"key": "DF_INFRA_URL", "field_name": "infra_url", "value": infra_url}]}


def test_ssl_on_updates_port_when_different(mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.side_effect = _env_values({"infra_port": "9000"})

    ssl_on(**{**default_ssl_kwargs, "port": 8080})

    assert mock.call(mock.ANY, "infra_port", "8080", quiet=True) in mocks.env_set.call_args_list
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_talks_to_admin_api_on_port_before_change(
    mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.side_effect = _env_values({"infra_port": "9000", "infra_admin_api_key": "admin-key"})

    ssl_on(**{**default_ssl_kwargs, "port": 8080})

    assert mocks.admin_request.call_args_list[0] == mock.call(
        "GET", "http://localhost:9000/admin/config", "http://localhost:9000", "admin-key"
    )


def test_ssl_on_converts_config_json_url_to_https(mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.side_effect = _env_values({"infra_port": "8086", "infra_url": "http://infra:8086"})
    mocks.admin_request.return_value = _config_with_infra_url("http://infra.example.com:8086")

    ssl_on(**default_ssl_kwargs)

    assert mocks.admin_request.call_count == 2
    assert mocks.admin_request.call_args == mock.call(
        "PUT",
        "http://localhost:8086/admin/config",
        "http://localhost:8086",
        "",
        json_body={"infra_url": "https://infra.example.com:8086"},
    )
    assert (
        mock.call(mock.ANY, "infra_url", "https://infra.example.com:8086", quiet=True) in mocks.env_set.call_args_list
    )


def test_ssl_on_falls_back_to_env_url_when_config_json_has_none(
    mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.side_effect = _env_values({"infra_url": "http://localhost:8080"})

    ssl_on(**default_ssl_kwargs)

    assert mocks.admin_request.call_args.kwargs["json_body"] == {"infra_url": "https://localhost:8080"}
    assert mock.call(mock.ANY, "infra_url", "https://localhost:8080", quiet=True) in mocks.env_set.call_args_list


def test_ssl_on_uses_provided_server_directly(mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.side_effect = _env_values({"infra_url": "http://localhost:8080"})
    mocks.admin_request.return_value = _config_with_infra_url("http://localhost:8080")

    ssl_on(**{**default_ssl_kwargs, "server": "https://myserver.com"})

    assert mocks.admin_request.call_args.kwargs["json_body"] == {"infra_url": "https://myserver.com"}
    assert mock.call(mock.ANY, "infra_url", "https://myserver.com", quiet=True) in mocks.env_set.call_args_list
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_skips_url_writes_when_already_https(
    mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.side_effect = _env_values({"infra_url": "https://infra:8086"})
    mocks.admin_request.return_value = _config_with_infra_url("https://infra:8086")

    ssl_on(**default_ssl_kwargs)

    assert mocks.admin_request.call_count == 1
    assert all(c.args[1] != "infra_url" for c in mocks.env_set.call_args_list)


def test_ssl_on_enables_tls_through_uvicorn_env_in_compose(
    mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**default_ssl_kwargs)

    infra_service = compose_data["services"]["infra"]
    assert "command" not in infra_service
    assert "entrypoint" not in infra_service
    assert infra_service["environment"] == [
        "UVICORN_SSL_KEYFILE=/ssl/key.pem",
        "UVICORN_SSL_CERTFILE=/ssl/cert.pem",
    ]
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_runs_docker_compose_up(
    mocks: SimpleNamespace, tmp_path: Path, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**default_ssl_kwargs)

    assert any("up" in str(arg) and "--build" in str(arg) for arg in mocks.run.call_args_list)
    assert mocks.assert_docker.call_count == 1


def test_ssl_on_asks_for_url_with_https_default_when_server_omitted(
    mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.side_effect = _env_values({"infra_port": "8086"})
    mocks.admin_request.return_value = _config_with_infra_url("http://infra.example.com:8086")
    mocks.echo.prompt_until_valid.side_effect = None
    mocks.echo.prompt_until_valid.return_value = "https://df.example.com"

    ssl_on(**default_ssl_kwargs)

    assert mocks.echo.prompt_until_valid.call_args == mock.call(
        "Public https URL of DeepFellow Infra", validate_server, default="https://infra.example.com:8086"
    )
    assert mocks.admin_request.call_args.kwargs["json_body"] == {"infra_url": "https://df.example.com"}
    assert mock.call(mock.ANY, "infra_url", "https://df.example.com", quiet=True) in mocks.env_set.call_args_list


def test_ssl_on_skips_url_prompt_when_server_provided(
    mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**{**default_ssl_kwargs, "server": "https://df.example.com"})

    assert mocks.echo.prompt_until_valid.call_count == 0


def test_ssl_on_leaves_install_untouched_when_url_prompt_aborted(
    mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None
    mocks.echo.prompt_until_valid.side_effect = typer.Exit(1)

    with pytest.raises(typer.Exit):
        ssl_on(**default_ssl_kwargs)

    assert mocks.save.call_count == 0
    assert mocks.run.call_count == 0
    assert mocks.admin_request.call_count == 1
    assert mocks.env_set.call_count == 0


def test_ssl_on_warns_when_url_host_is_docker_service_name(
    mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.side_effect = _env_values({"infra_url": "http://infra:8086"})

    ssl_on(**default_ssl_kwargs)

    assert mocks.echo.warning.call_count == 1
    assert '"infra" in https://infra:8086 resolves only inside Docker' in mocks.echo.warning.call_args.args[0]


def test_ssl_on_does_not_warn_when_url_host_is_public(
    mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**{**default_ssl_kwargs, "server": "https://df.example.com"})

    assert mocks.echo.warning.call_count == 0


def test_ssl_on_names_self_signed_cert_after_url(mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**{**default_ssl_kwargs, "server": "https://10.0.0.5:8086"})

    openssl_args = next(c.args[0] for c in mocks.run.call_args_list if "openssl" in c.args[0])
    assert openssl_args[-4:] == [
        "-subj",
        "/CN=10.0.0.5",
        "-addext",
        "subjectAltName=DNS:localhost,IP:127.0.0.1,DNS:infra,IP:10.0.0.5",
    ]
