# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the server env set command."""

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.server.env_command.set import set


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    return tmp_path


@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_restarts_server_when_confirmed(
    mock_check: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    directory: Path,
) -> None:
    mock_echo.confirm.return_value = True

    set(directory=directory, env_name="DF_SOME_VAR", env_value="value", df_prefix=True)

    assert mock_env_set.call_count == 1
    assert mock_echo.confirm.call_count == 1
    assert mock_stop.call_count == 1
    assert mock_stop.call_args == mock.call(directory)
    assert mock_start.call_count == 1
    assert mock_start.call_args == mock.call(directory)


@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_skips_restart_when_declined(
    mock_check: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    directory: Path,
) -> None:
    mock_echo.confirm.return_value = False

    set(directory=directory, env_name="DF_SOME_VAR", env_value="value", df_prefix=True)

    assert mock_env_set.call_count == 1
    assert mock_echo.confirm.call_count == 1
    assert mock_stop.call_count == 0
    assert mock_start.call_count == 0


@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_confirm_has_default_true(
    mock_check: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    directory: Path,
) -> None:
    mock_echo.confirm.return_value = True

    set(directory=directory, env_name="DF_SOME_VAR", env_value="value", df_prefix=True)

    assert mock_echo.confirm.call_args == mock.call("Restart the server now to apply the change?", default=True)
