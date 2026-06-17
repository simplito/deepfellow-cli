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

from deepfellow.server.restart import restart


@pytest.fixture
def env_content() -> dict:
    return {"df_server_port": "8080"}


@mock.patch("deepfellow.server.restart.start_server")
@mock.patch("deepfellow.server.restart.stop_server")
@mock.patch("deepfellow.server.restart.echo.info")
@mock.patch("deepfellow.server.restart.read_env_file_to_dict")
@mock.patch("deepfellow.server.restart.check_server_directory")
def test_restart_calls_check_server_directory(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_stop_server: Mock,
    mock_start_server: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = env_content

    restart(directory=directory)

    assert mock_check.call_count == 1
    assert mock_check.call_args == ((directory,), {})


@mock.patch("deepfellow.server.restart.start_server")
@mock.patch("deepfellow.server.restart.stop_server")
@mock.patch("deepfellow.server.restart.echo.info")
@mock.patch("deepfellow.server.restart.read_env_file_to_dict")
@mock.patch("deepfellow.server.restart.check_server_directory")
def test_restart_stops_then_starts_server(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_stop_server: Mock,
    mock_start_server: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = env_content
    manager = Mock()
    manager.attach_mock(mock_stop_server, "stop_server")
    manager.attach_mock(mock_start_server, "start_server")

    restart(directory=directory)

    assert mock_stop_server.call_count == 1
    assert mock_stop_server.call_args == ((directory,), {})
    assert mock_start_server.call_count == 1
    assert mock_start_server.call_args == ((directory,), {})
    assert manager.mock_calls == [mock.call.stop_server(directory), mock.call.start_server(directory)]


@mock.patch("deepfellow.server.restart.start_server")
@mock.patch("deepfellow.server.restart.stop_server")
@mock.patch("deepfellow.server.restart.echo.info")
@mock.patch("deepfellow.server.restart.read_env_file_to_dict")
@mock.patch("deepfellow.server.restart.check_server_directory")
def test_echo_prints_restarting_message(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_stop_server: Mock,
    mock_start_server: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = env_content

    restart(directory=directory)

    assert mock_echo.call_args_list[0] == mock.call("Restarting DeepFellow Server")


@mock.patch("deepfellow.server.restart.start_server")
@mock.patch("deepfellow.server.restart.stop_server")
@mock.patch("deepfellow.server.restart.echo.info")
@mock.patch("deepfellow.server.restart.read_env_file_to_dict")
@mock.patch("deepfellow.server.restart.check_server_directory")
def test_echo_prints_port(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_stop_server: Mock,
    mock_start_server: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = env_content

    restart(directory=directory)

    assert mock_echo.call_args_list[1] == mock.call(
        f"DeepFellow Server started on http://localhost:{env_content['df_server_port']}"
    )
