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

from deepfellow.infra.restart import restart


@pytest.fixture
def env_content() -> dict:
    return {"df_infra_port": "8080"}


@mock.patch("deepfellow.infra.restart.start_infra")
@mock.patch("deepfellow.infra.restart.stop_infra")
@mock.patch("deepfellow.infra.restart.echo.info")
@mock.patch("deepfellow.infra.restart.read_env_file_to_dict")
@mock.patch("deepfellow.infra.restart.check_infra_directory")
def test_restart_calls_check_infra_directory(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_stop_infra: Mock,
    mock_start_infra: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = env_content

    restart(directory=directory)

    assert mock_check.call_count == 1
    assert mock_check.call_args == ((directory,), {})


@mock.patch("deepfellow.infra.restart.start_infra")
@mock.patch("deepfellow.infra.restart.stop_infra")
@mock.patch("deepfellow.infra.restart.echo.info")
@mock.patch("deepfellow.infra.restart.read_env_file_to_dict")
@mock.patch("deepfellow.infra.restart.check_infra_directory")
def test_restart_stops_then_starts_infra(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_stop_infra: Mock,
    mock_start_infra: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = env_content
    manager = Mock()
    manager.attach_mock(mock_stop_infra, "stop_infra")
    manager.attach_mock(mock_start_infra, "start_infra")

    restart(directory=directory)

    assert mock_stop_infra.call_count == 1
    assert mock_stop_infra.call_args == ((directory,), {})
    assert mock_start_infra.call_count == 1
    assert mock_start_infra.call_args == ((directory,), {})
    assert manager.mock_calls == [mock.call.stop_infra(directory), mock.call.start_infra(directory)]


@mock.patch("deepfellow.infra.restart.start_infra")
@mock.patch("deepfellow.infra.restart.stop_infra")
@mock.patch("deepfellow.infra.restart.echo.info")
@mock.patch("deepfellow.infra.restart.read_env_file_to_dict")
@mock.patch("deepfellow.infra.restart.check_infra_directory")
def test_echo_prints_restarting_message(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_stop_infra: Mock,
    mock_start_infra: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = env_content

    restart(directory=directory)

    assert mock_echo.call_args_list[0] == mock.call("Restarting DeepFellow Infra")


@mock.patch("deepfellow.infra.restart.start_infra")
@mock.patch("deepfellow.infra.restart.stop_infra")
@mock.patch("deepfellow.infra.restart.echo.info")
@mock.patch("deepfellow.infra.restart.read_env_file_to_dict")
@mock.patch("deepfellow.infra.restart.check_infra_directory")
def test_echo_prints_port(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_stop_infra: Mock,
    mock_start_infra: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = env_content

    restart(directory=directory)

    assert mock_echo.call_args_list[1] == mock.call(
        f"DeepFellow Infra started on http://localhost:{env_content['df_infra_port']}"
    )
