# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the server create_admin command."""

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.server.create_admin import create_admin


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    return tmp_path


@mock.patch("deepfellow.server.create_admin.create_admin_util")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_creates_admin_with_arguments(
    mock_check_server_directory: Mock,
    mock_create_admin_util: Mock,
    directory: Path,
):
    create_admin(directory=directory, name="Ada", email="ada@b.com", password="hunter2hunter")

    assert mock_create_admin_util.call_count == 1
    assert mock_create_admin_util.call_args == mock.call(directory, "Ada", "ada@b.com", "hunter2hunter")


@mock.patch("deepfellow.server.create_admin.create_admin_util")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_checks_directory_before_creating_admin(
    mock_check_server_directory: Mock,
    mock_create_admin_util: Mock,
    directory: Path,
):
    _mock_manager = Mock()
    _mock_manager.attach_mock(mock_check_server_directory, "check_server_directory")
    _mock_manager.attach_mock(mock_create_admin_util, "create_admin_util")

    create_admin(directory=directory, name="Ada", email="ada@b.com", password="hunter2hunter")

    assert _mock_manager.mock_calls == [
        mock.call.check_server_directory(directory),
        mock.call.create_admin_util(directory, "Ada", "ada@b.com", "hunter2hunter"),
    ]


@mock.patch("deepfellow.server.create_admin.create_admin_util")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_passes_none_arguments_through(
    mock_check_server_directory: Mock,
    mock_create_admin_util: Mock,
    directory: Path,
):
    create_admin(directory=directory, name=None, email=None, password=None)

    assert mock_check_server_directory.call_count == 1
    assert mock_check_server_directory.call_args == mock.call(directory)
    assert mock_create_admin_util.call_args == mock.call(directory, None, None, None)
