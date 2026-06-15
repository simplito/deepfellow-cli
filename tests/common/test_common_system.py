# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for common/system.py."""

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.state import state
from deepfellow.common.system import rmtree


@mock.patch("deepfellow.common.system.shutil.rmtree")
def test_rmtree_success(mock_shutil_rmtree: Mock, directory: Path) -> None:
    rmtree(directory)

    assert mock_shutil_rmtree.call_count == 1
    assert mock_shutil_rmtree.call_args == mock.call(directory)


@mock.patch("deepfellow.common.system.run")
@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.shutil.rmtree")
def test_rmtree_permission_error_yes_flag_sudo_succeeds(
    mock_shutil_rmtree: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_shutil_rmtree.side_effect = PermissionError
    mock_run.return_value = ""
    state.yes = True

    rmtree(directory)

    assert mock_echo.confirm.call_count == 0
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["sudo", "-n", "rm", "-rf", directory.as_posix()])


@mock.patch("deepfellow.common.system.run")
@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.shutil.rmtree")
def test_rmtree_permission_error_user_confirms_sudo_succeeds(
    mock_shutil_rmtree: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_shutil_rmtree.side_effect = PermissionError
    mock_echo.confirm.return_value = True
    mock_run.return_value = ""

    rmtree(directory)

    assert mock_echo.confirm.call_count == 1
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["sudo", "-n", "rm", "-rf", directory.as_posix()])


@mock.patch("deepfellow.common.system.run")
@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.shutil.rmtree")
def test_rmtree_permission_error_sudo_fails_raises_exit(
    mock_shutil_rmtree: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_shutil_rmtree.side_effect = PermissionError
    mock_echo.confirm.return_value = True
    mock_run.return_value = None

    with pytest.raises(typer.Exit):
        rmtree(directory)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        f"sudo rm -rf failed. Remove manually: sudo rm -rf {directory.as_posix()}"
    )


@mock.patch("deepfellow.common.system.run")
@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.shutil.rmtree")
def test_rmtree_permission_error_user_declines_sudo_raises_exit(
    mock_shutil_rmtree: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_shutil_rmtree.side_effect = PermissionError
    mock_echo.confirm.return_value = False

    with pytest.raises(typer.Exit):
        rmtree(directory)

    assert mock_run.call_count == 0
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(f"Remove manually: sudo rm -rf {directory.as_posix()}")
