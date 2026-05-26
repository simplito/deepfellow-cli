# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import typer

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


@pytest.fixture
def mocks():
    with (
        mock.patch("deepfellow.infra.ssl_on.shutil") as m_shutil,
        mock.patch("deepfellow.infra.ssl_on.run") as m_run,
        mock.patch("deepfellow.infra.ssl_on.env_set") as m_env_set,
        mock.patch("deepfellow.infra.ssl_on.env_get") as m_env_get,
        mock.patch("deepfellow.infra.ssl_on.save_compose_file") as m_save,
        mock.patch("deepfellow.infra.ssl_on.load_compose_file") as m_load,
        mock.patch("deepfellow.infra.ssl_on.is_service_running") as m_is_running,
        mock.patch("deepfellow.infra.ssl_on.echo") as m_echo,
        mock.patch("deepfellow.infra.ssl_on.check_infra_directory") as m_check,
    ):
        yield SimpleNamespace(
            shutil=m_shutil,
            run=m_run,
            env_set=m_env_set,
            env_get=m_env_get,
            save=m_save,
            load=m_load,
            is_running=m_is_running,
            echo=m_echo,
            check=m_check,
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


def test_ssl_on_errors_when_only_key_provided(mocks: SimpleNamespace, tmp_path: Path):
    with pytest.raises(typer.Exit):
        ssl_on(directory=tmp_path, ssl_key_path="/key.pem", ssl_cert_path="", port=None, server=None)

    assert mocks.echo.error.call_count == 1


def test_ssl_on_errors_when_only_cert_provided(mocks: SimpleNamespace, tmp_path: Path):
    with pytest.raises(typer.Exit):
        ssl_on(directory=tmp_path, ssl_key_path="", ssl_cert_path="/cert.pem", port=None, server=None)

    assert mocks.echo.error.call_count == 1


def test_ssl_on_errors_when_infra_not_running(mocks: SimpleNamespace, tmp_path: Path):
    mocks.is_running.return_value = False
    with pytest.raises(typer.Exit):
        ssl_on(directory=tmp_path, ssl_key_path="", ssl_cert_path="", port=None, server=None)

    assert mocks.echo.error.call_count == 1


def test_ssl_on_adds_ssl_volume_when_not_present(
    mocks: SimpleNamespace, tmp_path: Path, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**default_ssl_kwargs)

    ssl_dir_str = (tmp_path / "ssl").as_posix()

    assert f"{ssl_dir_str}:/ssl" in compose_data["services"]["infra"]["volumes"]


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


def test_ssl_on_saves_compose_twice(
    mocks: SimpleNamespace, tmp_path: Path, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**default_ssl_kwargs)

    assert mocks.save.call_count == 2


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


def test_ssl_on_copies_cert_files_when_paths_provided(
    mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**{**default_ssl_kwargs, "ssl_key_path": "/key.pem", "ssl_cert_path": "/cert.pem"})

    assert mocks.shutil.copy2.call_count == 2


def test_ssl_on_errors_when_cert_file_not_found(mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict):
    mocks.shutil.copy2.side_effect = FileNotFoundError("/key.pem")
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    with pytest.raises(typer.Exit):
        ssl_on(**{**default_ssl_kwargs, "ssl_key_path": "/key.pem", "ssl_cert_path": "/cert.pem"})

    assert mocks.echo.error.call_count == 1


def test_ssl_on_runs_openssl_when_no_paths_provided(
    mocks: SimpleNamespace, tmp_path: Path, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**default_ssl_kwargs)

    assert any("openssl" in str(arg) for arg in mocks.run.call_args_list)


def test_ssl_on_updates_port_when_different(mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.side_effect = [9000, None]

    ssl_on(**{**default_ssl_kwargs, "port": 8080})

    assert any("infra_port" in str(c) and "8080" in str(c) for c in mocks.env_set.call_args_list)


def test_ssl_on_converts_http_to_https(mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.side_effect = [None, "http://localhost:8080"]

    ssl_on(**default_ssl_kwargs)

    assert mock.call(mock.ANY, "infra_url", "https://localhost:8080", quiet=True) in mocks.env_set.call_args_list


def test_ssl_on_uses_provided_server_directly(mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.side_effect = [None, "http://localhost:8080"]

    ssl_on(**{**default_ssl_kwargs, "server": "https://myserver.com"})

    assert mock.call(mock.ANY, "infra_url", "https://myserver.com", quiet=True) in mocks.env_set.call_args_list


def test_ssl_on_sets_entrypoint_and_command_in_compose(
    mocks: SimpleNamespace, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**default_ssl_kwargs)

    assert compose_data["services"]["infra"]["entrypoint"] == []
    assert "--ssl-keyfile /ssl/key.pem" in compose_data["services"]["infra"]["command"]


def test_ssl_on_runs_docker_compose_up(
    mocks: SimpleNamespace, tmp_path: Path, compose_data: dict, default_ssl_kwargs: dict
):
    mocks.is_running.return_value = True
    mocks.load.return_value = compose_data
    mocks.env_get.return_value = None

    ssl_on(**default_ssl_kwargs)

    assert any("up" in str(arg) and "--build" in str(arg) for arg in mocks.run.call_args_list)
