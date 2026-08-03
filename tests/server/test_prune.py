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

from deepfellow.server.prune import prune

_DOWN_COMMAND = ["docker", "compose", "down", "-v"]


@mock.patch("deepfellow.server.prune.echo")
@mock.patch("deepfellow.server.prune.set_default_server_directory")
@mock.patch("deepfellow.server.prune.get_default_server_directory")
@mock.patch("deepfellow.server.prune.rmtree")
@mock.patch("deepfellow.server.prune.run")
@mock.patch("deepfellow.server.prune.assert_docker")
@mock.patch("deepfellow.server.prune.check_server_directory")
def test_prune_checks_server_directory(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    mock_get_default_server_directory.return_value = Path("/other/dir")

    prune(directory=directory)

    assert mock_check_server_directory.call_count == 1
    assert mock_check_server_directory.call_args == mock.call(directory)
    assert mock_assert_docker.call_count == 1
    assert mock_assert_docker.call_args == mock.call()


@mock.patch("deepfellow.server.prune.echo")
@mock.patch("deepfellow.server.prune.set_default_server_directory")
@mock.patch("deepfellow.server.prune.get_default_server_directory")
@mock.patch("deepfellow.server.prune.rmtree")
@mock.patch("deepfellow.server.prune.run")
@mock.patch("deepfellow.server.prune.assert_docker")
@mock.patch("deepfellow.server.prune.check_server_directory")
def test_prune_tears_down_stack_before_removing_files(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    mock_get_default_server_directory.return_value = Path("/other/dir")
    _mock_manager = Mock()
    _mock_manager.attach_mock(mock_run, "run")
    _mock_manager.attach_mock(mock_rmtree, "rmtree")

    prune(directory=directory)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(_DOWN_COMMAND, directory, quiet=True)
    assert mock_rmtree.call_count == 1
    assert mock_rmtree.call_args == mock.call(directory)
    assert _mock_manager.mock_calls == [
        mock.call.run(_DOWN_COMMAND, directory, quiet=True),
        mock.call.rmtree(directory),
    ]


@mock.patch("deepfellow.server.prune.echo")
@mock.patch("deepfellow.server.prune.set_default_server_directory")
@mock.patch("deepfellow.server.prune.get_default_server_directory")
@mock.patch("deepfellow.server.prune.rmtree")
@mock.patch("deepfellow.server.prune.run")
@mock.patch("deepfellow.server.prune.assert_docker")
@mock.patch("deepfellow.server.prune.check_server_directory")
def test_prune_resets_default_server_directory_when_matching(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    mock_get_default_server_directory.return_value = directory

    prune(directory=directory)

    assert mock_set_default_server_directory.call_count == 1
    assert mock_set_default_server_directory.call_args == mock.call("", True)


@mock.patch("deepfellow.server.prune.echo")
@mock.patch("deepfellow.server.prune.set_default_server_directory")
@mock.patch("deepfellow.server.prune.get_default_server_directory")
@mock.patch("deepfellow.server.prune.rmtree")
@mock.patch("deepfellow.server.prune.run")
@mock.patch("deepfellow.server.prune.assert_docker")
@mock.patch("deepfellow.server.prune.check_server_directory")
def test_prune_keeps_default_server_directory_when_not_matching(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    mock_get_default_server_directory.return_value = Path("/other/dir")

    prune(directory=directory)

    assert mock_set_default_server_directory.call_count == 0


@mock.patch("deepfellow.server.prune.echo")
@mock.patch("deepfellow.server.prune.set_default_server_directory")
@mock.patch("deepfellow.server.prune.get_default_server_directory")
@mock.patch("deepfellow.server.prune.rmtree")
@mock.patch("deepfellow.server.prune.run")
@mock.patch("deepfellow.server.prune.assert_docker")
@mock.patch("deepfellow.server.prune.check_server_directory")
def test_prune_reports_progress_in_order(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    mock_get_default_server_directory.return_value = Path("/other/dir")

    prune(directory=directory)

    assert mock_echo.info.call_args_list == [
        mock.call("Pruning DeepFellow Server."),
        mock.call("Removing DeepFellow Server containers and volumes."),
        mock.call("Removing DeepFellow Server files."),
    ]
    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == mock.call("DeepFellow Server pruned.")
