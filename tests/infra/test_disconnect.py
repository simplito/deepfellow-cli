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

from deepfellow.infra.disconnect import disconnect


def _config_with_parent(parent_infra_url: str | None) -> dict:
    entries = [{"key": "connect_to_mesh_url", "value": parent_infra_url}] if parent_infra_url else []
    return {"entries": entries}


@mock.patch("deepfellow.infra.disconnect.infra_admin_request")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_check_infra_directory(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_admin_request: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = ["8086", "admin-key"]
    mock_admin_request.return_value = _config_with_parent("http://parent-infra:8086")
    mock_echo.confirm.return_value = False

    disconnect(directory=directory)

    assert mock_check.call_count == 1
    assert mock_check.call_args == ((directory,), {})


@mock.patch("deepfellow.infra.disconnect.infra_admin_request")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_raises_exit_when_service_not_running(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_admin_request: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = False

    with pytest.raises(typer.Exit):
        disconnect(directory=directory)


@mock.patch("deepfellow.infra.disconnect.infra_admin_request")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_raises_exit_when_infra_port_missing(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_admin_request: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = [None, "admin-key"]

    with pytest.raises(typer.Exit):
        disconnect(directory=directory)

    assert mock_admin_request.call_count == 0


@mock.patch("deepfellow.infra.disconnect.infra_admin_request")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_infra_admin_request_to_read_config(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_admin_request: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = ["8086", "admin-key"]
    mock_admin_request.return_value = _config_with_parent(None)

    disconnect(directory=directory)

    assert mock_admin_request.call_args_list[0] == mock.call(
        "GET", "http://localhost:8086/admin/config", "http://localhost:8086", "admin-key"
    )


@mock.patch("deepfellow.infra.disconnect.infra_admin_request")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_echo_error_when_not_connected(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_admin_request: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = ["8086", "admin-key"]
    mock_admin_request.return_value = _config_with_parent(None)

    disconnect(directory=directory)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == (("Already disconnected",), {})


@mock.patch("deepfellow.infra.disconnect.infra_admin_request")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_does_not_put_config_when_not_connected(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_admin_request: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = ["8086", "admin-key"]
    mock_admin_request.return_value = _config_with_parent(None)

    disconnect(directory=directory)

    assert mock_admin_request.call_count == 1


@mock.patch("deepfellow.infra.disconnect.infra_admin_request")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_echo_success_when_not_confirmed(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_admin_request: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = ["8086", "admin-key"]
    mock_admin_request.return_value = _config_with_parent("http://parent-infra:8086")
    mock_echo.confirm.return_value = False

    disconnect(directory=directory)

    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == (("Operation ends with no changes.",), {})


@mock.patch("deepfellow.infra.disconnect.infra_admin_request")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_does_not_put_config_when_not_confirmed(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_admin_request: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = ["8086", "admin-key"]
    mock_admin_request.return_value = _config_with_parent("http://parent-infra:8086")
    mock_echo.confirm.return_value = False

    disconnect(directory=directory)

    assert mock_admin_request.call_count == 1


@mock.patch("deepfellow.infra.disconnect.infra_admin_request")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_infra_admin_request_to_clear_config_when_confirmed(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_admin_request: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = ["8086", "admin-key"]
    mock_admin_request.return_value = _config_with_parent("http://parent-infra:8086")
    mock_echo.confirm.return_value = True

    disconnect(directory=directory)

    assert mock_admin_request.call_args_list[1] == mock.call(
        "PUT",
        "http://localhost:8086/admin/config",
        "http://localhost:8086",
        "admin-key",
        json_body={"connect_to_mesh_url": "", "connect_to_mesh_key": ""},
    )


@mock.patch("deepfellow.infra.disconnect.infra_admin_request")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_echo_success_when_confirmed(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_admin_request: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = ["8086", "admin-key"]
    mock_admin_request.return_value = _config_with_parent("http://parent-infra:8086")
    mock_echo.confirm.return_value = True

    disconnect(directory=directory)

    assert mock_echo.success.call_count == 1
    assert "http://parent-infra:8086" in mock_echo.success.call_args[0][0]
