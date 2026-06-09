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

PARENT_URL = "http://parent-infra:8086"
MESH_KEY = "secret-mesh-key"
ADMIN_KEY = "admin-api-key"
INFRA_PORT = "8086"
LOCAL_URL = f"http://localhost:{INFRA_PORT}"
TOPOLOGY_URL = f"{LOCAL_URL}/admin/mesh/topology"


def _make_topology_response(root_url: str, you_are_here: bool = False) -> Mock:
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = [
        {"url": root_url, "you_are_here": you_are_here, "name": "infra", "models": [], "children": []}
    ]
    return response


@mock.patch("deepfellow.infra.connect.time.sleep")
@mock.patch("deepfellow.infra.connect.httpx.get")
def test_verify_parent_connection_success_on_first_poll(mock_get: Mock, mock_sleep: Mock) -> None:
    mock_get.return_value = _make_topology_response(PARENT_URL, you_are_here=False)

    result = _verify_parent_connection(LOCAL_URL, ADMIN_KEY)

    assert result == _VerifyResult.CONNECTED
    assert mock_get.call_count == 1
    assert mock_get.call_args == mock.call(
        TOPOLOGY_URL,
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        timeout=5,
    )
    assert mock_sleep.call_count == 0


@mock.patch("deepfellow.infra.connect.time.sleep")
@mock.patch("deepfellow.infra.connect.time.monotonic")
@mock.patch("deepfellow.infra.connect.httpx.get")
def test_verify_parent_connection_retries_until_connected(
    mock_get: Mock, mock_monotonic: Mock, mock_sleep: Mock
) -> None:
    # First call: you_are_here=True (not connected yet), second call: parent appears
    mock_monotonic.side_effect = [0, 1, 2, 3]  # deadline=60, first check at 1, second at 3
    not_connected = _make_topology_response("http://self:8086", you_are_here=True)
    connected = _make_topology_response(PARENT_URL, you_are_here=False)
    mock_get.side_effect = [not_connected, connected]

    result = _verify_parent_connection(LOCAL_URL, ADMIN_KEY)

    assert result == _VerifyResult.CONNECTED
    assert mock_get.call_count == 2
    assert mock_sleep.call_count == 1


@mock.patch("deepfellow.infra.connect.time.sleep")
@mock.patch("deepfellow.infra.connect.time.monotonic")
@mock.patch("deepfellow.infra.connect.httpx.get")
def test_verify_parent_connection_returns_timeout(mock_get: Mock, mock_monotonic: Mock, mock_sleep: Mock) -> None:
    mock_monotonic.side_effect = [0, 11]
    mock_get.return_value = _make_topology_response("http://self:8086", you_are_here=True)

    result = _verify_parent_connection(LOCAL_URL, ADMIN_KEY)

    assert result == _VerifyResult.TIMEOUT


@mock.patch("deepfellow.infra.connect.time.sleep")
@mock.patch("deepfellow.infra.connect.time.monotonic")
@mock.patch("deepfellow.infra.connect.httpx.get")
def test_verify_parent_connection_skips_http_errors(mock_get: Mock, mock_monotonic: Mock, mock_sleep: Mock) -> None:
    mock_monotonic.side_effect = [0, 1, 2, 3]
    mock_get.side_effect = [httpx.ConnectError("refused"), _make_topology_response(PARENT_URL)]

    result = _verify_parent_connection(LOCAL_URL, ADMIN_KEY)

    assert result == _VerifyResult.CONNECTED
    assert mock_sleep.call_count == 1


@mock.patch("deepfellow.infra.connect.time.sleep")
@mock.patch("deepfellow.infra.connect.time.monotonic")
@mock.patch("deepfellow.infra.connect.httpx.get")
def test_verify_parent_connection_returns_outdated_after_3_html_responses(
    mock_get: Mock, mock_monotonic: Mock, mock_sleep: Mock
) -> None:
    mock_monotonic.side_effect = [0, 1, 2, 3, 4]
    html_response = Mock(spec=httpx.Response)
    html_response.status_code = 200
    html_response.json.side_effect = JSONDecodeError("Expecting value", "", 0)
    mock_get.return_value = html_response

    result = _verify_parent_connection(LOCAL_URL, ADMIN_KEY)

    assert result == _VerifyResult.OUTDATED


@mock.patch("deepfellow.infra.connect.time.sleep")
@mock.patch("deepfellow.infra.connect.time.monotonic")
@mock.patch("deepfellow.infra.connect.httpx.get")
def test_verify_parent_connection_resets_non_json_count_on_success(
    mock_get: Mock, mock_monotonic: Mock, mock_sleep: Mock
) -> None:
    # deadline=10; 7 monotonic calls: 1 initial + 1 per iteration (6 iters)
    mock_monotonic.side_effect = [0, 1, 2, 3, 4, 5, 6]
    html = Mock(spec=httpx.Response)
    html.status_code = 200
    html.json.side_effect = JSONDecodeError("", "", 0)
    # good resets count to 0 (you_are_here=True → not connected, keep looping)
    good = _make_topology_response("http://self:8086", you_are_here=True)
    mock_get.side_effect = [html, html, good, html, html, html]

    result = _verify_parent_connection(LOCAL_URL, ADMIN_KEY)

    assert result == _VerifyResult.OUTDATED


# --- connect command integration tests ---


@mock.patch("deepfellow.infra.connect._verify_parent_connection")
@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
@mock.patch("deepfellow.infra.connect.echo")
def test_connect_success(
    mock_echo: Mock,
    mock_check: Mock,
    mock_running: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_verify: Mock,
    directory: Path,
) -> None:
    mock_running.return_value = True
    mock_env_get.side_effect = lambda f, key, **kw: {
        "DF_CONNECT_TO_MESH_URL": None,
        "DF_INFRA_PORT": INFRA_PORT,
        "DF_INFRA_ADMIN_API_KEY": ADMIN_KEY,
    }.get(key)
    mock_verify.return_value = _VerifyResult.CONNECTED

    connect(directory=directory, parent_infra_url=PARENT_URL, mesh_key=MESH_KEY)

    assert mock_verify.call_count == 1
    assert mock_verify.call_args == mock.call(LOCAL_URL, ADMIN_KEY)
    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == mock.call(f"DeepFellow Infra is connected to another Infra at {PARENT_URL}")


@mock.patch("deepfellow.infra.connect._verify_parent_connection")
@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
@mock.patch("deepfellow.infra.connect.echo")
def test_connect_fails_when_verification_times_out(
    mock_echo: Mock,
    mock_check: Mock,
    mock_running: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_verify: Mock,
    directory: Path,
) -> None:
    mock_running.return_value = True
    mock_env_get.side_effect = lambda f, key, **kw: {
        "DF_CONNECT_TO_MESH_URL": None,
        "DF_INFRA_PORT": INFRA_PORT,
        "DF_INFRA_ADMIN_API_KEY": ADMIN_KEY,
    }.get(key)
    mock_verify.return_value = _VerifyResult.TIMEOUT

    with pytest.raises(typer.Exit):
        connect(directory=directory, parent_infra_url=PARENT_URL, mesh_key=MESH_KEY)

    assert mock_echo.error.call_count == 1
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.connect._verify_parent_connection")
@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
@mock.patch("deepfellow.infra.connect.echo")
def test_connect_warns_when_infra_outdated(
    mock_echo: Mock,
    mock_check: Mock,
    mock_running: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_verify: Mock,
    directory: Path,
) -> None:
    mock_running.return_value = True
    mock_env_get.side_effect = lambda f, key, **kw: {
        "DF_CONNECT_TO_MESH_URL": None,
        "DF_INFRA_PORT": INFRA_PORT,
        "DF_INFRA_ADMIN_API_KEY": ADMIN_KEY,
    }.get(key)
    mock_verify.return_value = _VerifyResult.OUTDATED

    connect(directory=directory, parent_infra_url=PARENT_URL, mesh_key=MESH_KEY)

    assert mock_echo.warning.call_count == 1
    assert mock_echo.error.call_count == 0
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.connect._verify_parent_connection")
@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
@mock.patch("deepfellow.infra.connect.echo")
def test_connect_skips_verification_when_port_missing(
    mock_echo: Mock,
    mock_check: Mock,
    mock_running: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_verify: Mock,
    directory: Path,
) -> None:
    mock_running.return_value = True
    mock_env_get.side_effect = lambda f, key, **kw: {
        "DF_CONNECT_TO_MESH_URL": None,
        "DF_INFRA_PORT": None,
        "DF_INFRA_ADMIN_API_KEY": ADMIN_KEY,
    }.get(key)

    connect(directory=directory, parent_infra_url=PARENT_URL, mesh_key=MESH_KEY)

    assert mock_verify.call_count == 0
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
@mock.patch("deepfellow.infra.connect.echo")
def test_connect_exits_when_infra_not_running(
    mock_echo: Mock,
    mock_check: Mock,
    mock_running: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_running.return_value = False

    with pytest.raises(typer.Exit):
        connect(directory=directory, parent_infra_url=PARENT_URL, mesh_key=MESH_KEY)

    assert mock_echo.error.call_count == 1
    assert mock_run.call_count == 0


# --- _is_localhost_url unit tests ---


def test_is_localhost_url_true_for_127() -> None:
    assert _is_localhost_url("ws://127.0.0.1:8088") is True


def test_is_localhost_url_true_for_localhost() -> None:
    assert _is_localhost_url("http://localhost:8086") is True


def test_is_localhost_url_false_for_external() -> None:
    assert _is_localhost_url("ws://host.docker.internal:8088") is False


def test_is_localhost_url_false_for_named_host() -> None:
    assert _is_localhost_url("http://infra:8086") is False


@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
@mock.patch("deepfellow.infra.connect.echo")
def test_connect_exits_for_localhost_url(
    mock_echo: Mock,
    mock_check: Mock,
    mock_running: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_running.return_value = True

    with pytest.raises(typer.Exit):
        connect(directory=directory, parent_infra_url="ws://127.0.0.1:8088", mesh_key=MESH_KEY)

    assert mock_echo.error.call_count == 1
    assert mock_run.call_count == 0
    error_msg = mock_echo.error.call_args[0][0]
    assert "host.docker.internal" in error_msg


# --- LEGACY result tests ---


@mock.patch("deepfellow.infra.connect._logs_show_connection")
@mock.patch("deepfellow.infra.connect._verify_parent_connection")
@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
@mock.patch("deepfellow.infra.connect.echo")
def test_connect_legacy_warns_and_succeeds_when_logs_show_connection(
    mock_echo: Mock,
    mock_check: Mock,
    mock_running: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_verify: Mock,
    mock_logs: Mock,
    directory: Path,
) -> None:
    mock_running.return_value = True
    mock_env_get.side_effect = lambda f, key, **kw: {
        "DF_CONNECT_TO_MESH_URL": None,
        "DF_INFRA_PORT": INFRA_PORT,
        "DF_INFRA_ADMIN_API_KEY": ADMIN_KEY,
    }.get(key)
    mock_verify.return_value = _VerifyResult.LEGACY
    mock_logs.return_value = True

    connect(directory=directory, parent_infra_url=PARENT_URL, mesh_key=MESH_KEY)

    assert mock_echo.warning.call_count == 1
    assert mock_echo.error.call_count == 0
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.connect._logs_show_connection")
@mock.patch("deepfellow.infra.connect._verify_parent_connection")
@mock.patch("deepfellow.infra.connect.run")
@mock.patch("deepfellow.infra.connect.env_set")
@mock.patch("deepfellow.infra.connect.env_get")
@mock.patch("deepfellow.infra.connect.is_service_running")
@mock.patch("deepfellow.infra.connect.check_infra_directory")
@mock.patch("deepfellow.infra.connect.echo")
def test_connect_legacy_fails_when_logs_show_no_connection(
    mock_echo: Mock,
    mock_check: Mock,
    mock_running: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_verify: Mock,
    mock_logs: Mock,
    directory: Path,
) -> None:
    mock_running.return_value = True
    mock_env_get.side_effect = lambda f, key, **kw: {
        "DF_CONNECT_TO_MESH_URL": None,
        "DF_INFRA_PORT": INFRA_PORT,
        "DF_INFRA_ADMIN_API_KEY": ADMIN_KEY,
    }.get(key)
    mock_verify.return_value = _VerifyResult.LEGACY
    mock_logs.return_value = False

    with pytest.raises(typer.Exit):
        connect(directory=directory, parent_infra_url=PARENT_URL, mesh_key=MESH_KEY)

    assert mock_echo.error.call_count == 1
    assert mock_echo.success.call_count == 0


# --- _logs_show_connection unit tests ---


@mock.patch("deepfellow.infra.connect.run")
def test_logs_show_connection_true_when_setup_after_disconnect(mock_run: Mock, directory: Path) -> None:
    mock_run.return_value = "\n".join(
        [
            "WS client disconnected",
            "WS client connected",
            "WS client setup finished",
        ]
    )
    assert _logs_show_connection(directory) is True


@mock.patch("deepfellow.infra.connect.run")
def test_logs_show_connection_false_when_disconnect_after_setup(mock_run: Mock, directory: Path) -> None:
    mock_run.return_value = "\n".join(
        [
            "WS client connected",
            "WS client setup finished",
            "WS client disconnected",
        ]
    )
    assert _logs_show_connection(directory) is False


@mock.patch("deepfellow.infra.connect.run")
def test_logs_show_connection_false_when_no_setup_line(mock_run: Mock, directory: Path) -> None:
    mock_run.return_value = "Application startup complete.\nSome other log line."
    assert _logs_show_connection(directory) is False


@mock.patch("deepfellow.infra.connect.run")
def test_logs_show_connection_false_on_exception(mock_run: Mock, directory: Path) -> None:
    mock_run.side_effect = RuntimeError("docker error")
    assert _logs_show_connection(directory) is False
