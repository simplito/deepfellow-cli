# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.state import state
from deepfellow.prune import _prune_service, prune

_UV_UNINSTALL_CMD = ["uv", "tool", "uninstall", "deepfellow-cli"]


@mock.patch("deepfellow.prune.rmtree")
@mock.patch("deepfellow.prune._down_docker_compose")
@mock.patch("deepfellow.prune.echo")
def test_prune_service_tears_down_when_directory_exists(mock_echo: Mock, mock_down: Mock, mock_rmtree: Mock) -> None:
    directory = Mock()
    directory.exists.return_value = True

    _prune_service("Server", directory)

    assert mock_down.call_count == 1
    assert mock_down.call_args == mock.call(directory)
    assert mock_rmtree.call_count == 1
    assert mock_rmtree.call_args == mock.call(directory)
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.prune.rmtree")
@mock.patch("deepfellow.prune._down_docker_compose")
@mock.patch("deepfellow.prune.echo")
def test_prune_service_skips_when_directory_missing(mock_echo: Mock, mock_down: Mock, mock_rmtree: Mock) -> None:
    directory = Mock()
    directory.exists.return_value = False

    _prune_service("Infra", directory)

    assert mock_down.call_count == 0
    assert mock_rmtree.call_count == 0


@mock.patch("deepfellow.prune.DF_DEEPFELLOW_DIRECTORY")
@mock.patch("deepfellow.prune.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.prune.get_default_server_directory")
@mock.patch("deepfellow.prune.rmtree")
@mock.patch("deepfellow.prune._down_docker_compose")
@mock.patch("deepfellow.prune.echo")
@mock.patch("deepfellow.prune.run", return_value="ok")
@mock.patch("deepfellow.prune._get_uninstall_command", return_value=_UV_UNINSTALL_CMD)
def test_prune_tears_down_everything_with_yes_flag(
    mock_get: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_down: Mock,
    mock_rmtree: Mock,
    mock_server_dir: Mock,
    mock_infra_dir: Mock,
    mock_deepfellow_dir: Mock,
) -> None:
    server_dir = mock_server_dir.return_value
    server_dir.exists.return_value = True
    mock_infra_dir.exists.return_value = True
    mock_deepfellow_dir.exists.return_value = True
    state.yes = True

    prune()

    assert mock_down.call_count == 2
    assert mock_rmtree.call_count == 3
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(_UV_UNINSTALL_CMD)
    assert mock_echo.success.call_count == 4

    state.reset()


@mock.patch("deepfellow.prune.echo")
@mock.patch("deepfellow.prune._get_uninstall_command", return_value=_UV_UNINSTALL_CMD)
def test_prune_exits_when_user_declines_confirmation(mock_get: Mock, mock_echo: Mock) -> None:
    mock_echo.confirm.return_value = False
    state.yes = False

    with pytest.raises(typer.Exit) as exc_info:
        prune()

    assert exc_info.value.exit_code == 0

    state.reset()


@mock.patch("deepfellow.prune.DF_DEEPFELLOW_DIRECTORY")
@mock.patch("deepfellow.prune.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.prune.get_default_server_directory")
@mock.patch("deepfellow.prune.rmtree")
@mock.patch("deepfellow.prune._down_docker_compose")
@mock.patch("deepfellow.prune.echo")
@mock.patch("deepfellow.prune.run", return_value="ok")
@mock.patch("deepfellow.prune._get_uninstall_command", return_value=_UV_UNINSTALL_CMD)
def test_prune_skips_missing_installations(
    mock_get: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_down: Mock,
    mock_rmtree: Mock,
    mock_server_dir: Mock,
    mock_infra_dir: Mock,
    mock_deepfellow_dir: Mock,
) -> None:
    mock_server_dir.return_value.exists.return_value = False
    mock_infra_dir.exists.return_value = False
    mock_deepfellow_dir.exists.return_value = False
    state.yes = True

    prune()

    assert mock_down.call_count == 0
    assert mock_rmtree.call_count == 0
    assert mock_run.call_count == 1

    state.reset()


@mock.patch("deepfellow.prune.DF_DEEPFELLOW_DIRECTORY")
@mock.patch("deepfellow.prune.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.prune.get_default_server_directory")
@mock.patch("deepfellow.prune.rmtree")
@mock.patch("deepfellow.prune._down_docker_compose")
@mock.patch("deepfellow.prune.echo")
@mock.patch("deepfellow.prune.run")
@mock.patch("deepfellow.prune._get_uninstall_command", return_value=None)
def test_prune_warns_and_skips_package_removal_when_no_package_manager(
    mock_get: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_down: Mock,
    mock_rmtree: Mock,
    mock_server_dir: Mock,
    mock_infra_dir: Mock,
    mock_deepfellow_dir: Mock,
) -> None:
    mock_server_dir.return_value.exists.return_value = False
    mock_infra_dir.exists.return_value = False
    mock_deepfellow_dir.exists.return_value = True
    state.yes = True

    prune()

    assert mock_rmtree.call_count == 1
    assert mock_run.call_count == 0
    assert mock_echo.warning.call_count == 1

    state.reset()
