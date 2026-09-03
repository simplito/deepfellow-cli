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
import typer

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
    assert mock_create_admin_util.call_args == mock.call(
        directory, "Ada", "ada@b.com", "hunter2hunter", silent_if_exists=True
    )


@mock.patch("deepfellow.server.create_admin.create_admin_util")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_checks_directory_before_creating_admin(
    mock_check_server_directory: Mock,
    mock_create_admin_util: Mock,
    directory: Path,
):
    mock_create_admin_util.return_value = True
    _mock_manager = Mock()
    _mock_manager.attach_mock(mock_check_server_directory, "check_server_directory")
    _mock_manager.attach_mock(mock_create_admin_util, "create_admin_util")

    create_admin(directory=directory, name="Ada", email="ada@b.com", password="hunter2hunter")

    assert _mock_manager.mock_calls == [
        mock.call.check_server_directory(directory),
        mock.call.create_admin_util(directory, "Ada", "ada@b.com", "hunter2hunter", silent_if_exists=True),
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
    assert mock_create_admin_util.call_args == mock.call(directory, None, None, None, silent_if_exists=True)


@mock.patch("deepfellow.server.create_admin.echo")
@mock.patch("deepfellow.server.create_admin.create_admin_util")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_succeeds_when_admin_is_newly_created(
    mock_check_server_directory: Mock,
    mock_create_admin_util: Mock,
    mock_echo: Mock,
    directory: Path,
):
    mock_create_admin_util.return_value = True

    create_admin(directory=directory, name="Ada", email="ada@b.com", password="hunter2hunter")

    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.server.create_admin.echo")
@mock.patch("deepfellow.server.create_admin.create_admin_util")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_exits_with_error_when_admin_already_exists(
    mock_check_server_directory: Mock,
    mock_create_admin_util: Mock,
    mock_echo: Mock,
    directory: Path,
):
    """Unlike suite install's/a --template reinstall's own create-admin step, this direct command
    has no resume context - an existing admin means IT failed to do what was asked, not a no-op."""
    mock_create_admin_util.return_value = False

    with pytest.raises(typer.Exit):
        create_admin(directory=directory, name="Ada", email="ada@b.com", password="hunter2hunter")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "Unable to create an admin: an account with that email already exists."
    )
