# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from json import JSONDecodeError
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import httpx
import pytest
import typer

from deepfellow.infra.connect import (
    _is_localhost_url,
    _logs_show_connection,
    _verify_parent_connection,
    _VerifyResult,
    connect,
)


@pytest.fixture
def default_connect_kwargs(directory: Path) -> dict:
    return {
        "directory": directory,
        "parent_infra_url": "http://parent-infra:8086",
        "mesh_key": "test-mesh-key",
    }


@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_calls_check_infra_directory(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    default_connect_kwargs: dict,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = None

    connect(**default_connect_kwargs)

    assert mock_check.call_count == 1
    assert mock_check.call_args == ((directory,), {})


@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_raises_exit_when_service_not_running(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    default_connect_kwargs: dict,
) -> None:
    mock_is_running.return_value = False

    with pytest.raises(typer.Exit):
        connect(**default_connect_kwargs)


@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_calls_env_get(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    default_connect_kwargs: dict,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = None

    connect(**default_connect_kwargs)

    assert mock_env_get.call_args_list[0] == ((directory / ".env", "DF_CONNECT_TO_MESH_URL"), {})


@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_prints_disconnect_message_when_previous_url_exists(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    default_connect_kwargs: dict,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = ["http://old-infra:8086", None, None]

    connect(**default_connect_kwargs)

    echo_info_messages = [call.args[0] for call in mock_echo.info.call_args_list]
    assert any("http://old-infra:8086" in msg for msg in echo_info_messages)


@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_no_disconnect_message_when_no_previous_url(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    default_connect_kwargs: dict,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = None

    connect(**default_connect_kwargs)

    echo_info_messages = [call.args[0] for call in mock_echo.info.call_args_list]
    assert not any("Disconnecting" in msg for msg in echo_info_messages)


@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_calls_env_set_for_mesh_url(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    default_connect_kwargs: dict,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = None

    connect(**default_connect_kwargs)

    assert (
        mock.call(directory / ".env", "DF_CONNECT_TO_MESH_URL", "ws://parent-infra:8086") in mock_env_set.call_args_list
    )


@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_calls_env_set_for_mesh_key(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    default_connect_kwargs: dict,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = None

    connect(**default_connect_kwargs)

    assert mock.call(directory / ".env", "DF_CONNECT_TO_MESH_KEY", "test-mesh-key") in mock_env_set.call_args_list


@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_calls_docker_compose_down(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    default_connect_kwargs: dict,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = None

    connect(**default_connect_kwargs)

    assert mock.call(["docker", "compose", "down"], cwd=directory, quiet=True) in mock_run.call_args_list


@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_calls_docker_compose_up(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    default_connect_kwargs: dict,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = None

    connect(**default_connect_kwargs)

    assert (
        mock.call(["docker", "compose", "up", "-d", "--remove-orphans"], cwd=directory, quiet=True)
        in mock_run.call_args_list
    )


@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_calls_echo_success(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    default_connect_kwargs: dict,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = None

    connect(**default_connect_kwargs)

    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.connect.urlparse")
def test_is_localhost_url_returns_false_on_exception(mock_urlparse: Mock) -> None:
    mock_urlparse.side_effect = Exception("parse error")

    assert _is_localhost_url("not-a-url") is False


@mock.patch("deepfellow.infra.connect.run")
def test_logs_show_connection_returns_true(mock_run: Mock, directory: Path) -> None:
    mock_run.return_value = "WS client disconnected\nWS client setup finished"

    assert _logs_show_connection(directory) is True


@mock.patch("deepfellow.infra.connect.run")
def test_logs_show_connection_returns_false_when_disconnect_after_setup(mock_run: Mock, directory: Path) -> None:
    mock_run.return_value = "WS client setup finished\nWS client disconnected"

    assert _logs_show_connection(directory) is False


@mock.patch("deepfellow.infra.connect.run")
def test_logs_show_connection_returns_false_on_exception(mock_run: Mock, directory: Path) -> None:
    mock_run.side_effect = Exception("docker error")

    assert _logs_show_connection(directory) is False


@mock.patch("deepfellow.infra.connect.time")
@mock.patch("deepfellow.infra.connect.httpx.get")
def test_verify_parent_connection_returns_connected(mock_get: Mock, mock_time: Mock) -> None:
    mock_time.monotonic.side_effect = [0, 0, 5]
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"you_are_here": False}]
    mock_get.return_value = mock_response

    assert _verify_parent_connection("http://localhost:8086", "key") == _VerifyResult.CONNECTED


@mock.patch("deepfellow.infra.connect.time")
@mock.patch("deepfellow.infra.connect.httpx.get")
def test_verify_parent_connection_returns_timeout(mock_get: Mock, mock_time: Mock) -> None:
    mock_time.monotonic.side_effect = [0, 0, 5, 5, 61]
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    assert _verify_parent_connection("http://localhost:8086", "key") == _VerifyResult.TIMEOUT


@mock.patch("deepfellow.infra.connect.time")
@mock.patch("deepfellow.infra.connect.httpx.get")
def test_verify_parent_connection_returns_legacy(mock_get: Mock, mock_time: Mock) -> None:
    mock_time.monotonic.side_effect = [0, 0, 5, 5, 61]
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"you_are_here": True}]
    mock_get.return_value = mock_response

    assert _verify_parent_connection("http://localhost:8086", "key") == _VerifyResult.LEGACY


@mock.patch("deepfellow.infra.connect.time")
@mock.patch("deepfellow.infra.connect.httpx.get")
def test_verify_parent_connection_returns_outdated(mock_get: Mock, mock_time: Mock) -> None:
    mock_time.monotonic.side_effect = [0, 0, 5, 5, 5, 5, 5]
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.side_effect = JSONDecodeError("msg", "doc", 0)
    mock_get.return_value = mock_response

    assert _verify_parent_connection("http://localhost:8086", "key") == _VerifyResult.OUTDATED


@mock.patch("deepfellow.infra.connect.time")
@mock.patch("deepfellow.infra.connect.httpx.get")
def test_verify_parent_connection_handles_http_error_and_returns_timeout(mock_get: Mock, mock_time: Mock) -> None:
    mock_time.monotonic.side_effect = [0, 0, 5, 5, 61]
    mock_get.side_effect = httpx.HTTPError("connection refused")

    assert _verify_parent_connection("http://localhost:8086", "key") == _VerifyResult.TIMEOUT


@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.time")
@mock.patch("deepfellow.infra.connect.httpx.get")
def test_verify_parent_connection_prints_slow_warning_once(mock_get: Mock, mock_time: Mock, mock_echo: Mock) -> None:
    mock_time.monotonic.side_effect = [0, 0, 5, 5, 11, 11, 15, 61]
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    _verify_parent_connection("http://localhost:8086", "key")

    assert mock_echo.info.call_count == 1


@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_raises_exit_when_localhost_url(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True

    with pytest.raises(typer.Exit):
        connect(directory=directory, parent_infra_url="http://localhost:8086", mesh_key="key")


@mock.patch("deepfellow.infra.connect._verify_parent_connection")
@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_warns_on_outdated_verification(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_verify: Mock,
    default_connect_kwargs: dict,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = [None, "8086", "admin-key"]
    mock_verify.return_value = _VerifyResult.OUTDATED

    connect(**default_connect_kwargs)

    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.infra.connect._logs_show_connection")
@mock.patch("deepfellow.infra.connect._verify_parent_connection")
@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_warns_on_legacy_verification_with_logs(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_verify: Mock,
    mock_logs: Mock,
    default_connect_kwargs: dict,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = [None, "8086", "admin-key"]
    mock_verify.return_value = _VerifyResult.LEGACY
    mock_logs.return_value = True

    connect(**default_connect_kwargs)

    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.infra.connect._logs_show_connection")
@mock.patch("deepfellow.infra.connect._verify_parent_connection")
@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_raises_exit_on_legacy_verification_without_logs(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_verify: Mock,
    mock_logs: Mock,
    default_connect_kwargs: dict,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = [None, "8086", "admin-key"]
    mock_verify.return_value = _VerifyResult.LEGACY
    mock_logs.return_value = False

    with pytest.raises(typer.Exit):
        connect(**default_connect_kwargs)


@mock.patch("deepfellow.infra.connect._verify_parent_connection")
@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_raises_exit_on_timeout_verification(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_verify: Mock,
    default_connect_kwargs: dict,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = [None, "8086", "admin-key"]
    mock_verify.return_value = _VerifyResult.TIMEOUT

    with pytest.raises(typer.Exit):
        connect(**default_connect_kwargs)


@mock.patch("deepfellow.infra.connect._verify_parent_connection")
@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.echo")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
def test_connect_calls_echo_success_after_connected_verification(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_verify: Mock,
    default_connect_kwargs: dict,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.side_effect = [None, "8086", "admin-key"]
    mock_verify.return_value = _VerifyResult.CONNECTED

    connect(**default_connect_kwargs)

    assert mock_echo.success.call_count == 1
