# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the server password_reset command."""

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.server.password_reset import password_reset


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    return tmp_path


@mock.patch("deepfellow.server.password_reset.reset_password_util")
@mock.patch("deepfellow.server.password_reset.check_server_directory")
def test_password_reset_resets_password_with_arguments(
    mock_check_server_directory: Mock,
    mock_reset_password_util: Mock,
    directory: Path,
):
    password_reset(directory=directory, email="ada@b.com", password="hunter2hunter")

    assert mock_reset_password_util.call_count == 1
    assert mock_reset_password_util.call_args == mock.call(directory, "ada@b.com", "hunter2hunter")


@mock.patch("deepfellow.server.password_reset.reset_password_util")
@mock.patch("deepfellow.server.password_reset.check_server_directory")
def test_password_reset_checks_directory_before_resetting_password(
    mock_check_server_directory: Mock,
    mock_reset_password_util: Mock,
    directory: Path,
):
    _mock_manager = Mock()
    _mock_manager.attach_mock(mock_check_server_directory, "check_server_directory")
    _mock_manager.attach_mock(mock_reset_password_util, "reset_password_util")

    password_reset(directory=directory, email="ada@b.com", password="hunter2hunter")

    assert _mock_manager.mock_calls == [
        mock.call.check_server_directory(directory),
        mock.call.reset_password_util(directory, "ada@b.com", "hunter2hunter"),
    ]


@mock.patch("deepfellow.server.password_reset.reset_password_util")
@mock.patch("deepfellow.server.password_reset.check_server_directory")
def test_password_reset_passes_none_arguments_through(
    mock_check_server_directory: Mock,
    mock_reset_password_util: Mock,
    directory: Path,
):
    password_reset(directory=directory, email=None, password=None)

    assert mock_check_server_directory.call_count == 1
    assert mock_check_server_directory.call_args == mock.call(directory)
    assert mock_reset_password_util.call_args == mock.call(directory, None, None)
