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

from deepfellow.infra.prune import prune

_DOWN_COMMAND = ["docker", "compose", "down", "-v"]


@mock.patch("deepfellow.infra.prune.rmtree")
@mock.patch("deepfellow.infra.prune.run")
@mock.patch("deepfellow.infra.prune.echo")
@mock.patch("deepfellow.infra.prune.assert_docker")
@mock.patch("deepfellow.infra.prune.check_infra_directory")
def test_prune_checks_directory_and_docker_before_pruning(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    directory: Path,
) -> None:
    prune(directory=directory)

    assert mock_check.call_count == 1
    assert mock_check.call_args == mock.call(directory)
    assert mock_assert_docker.call_count == 1
    assert mock_assert_docker.call_args == mock.call()


@mock.patch("deepfellow.infra.prune.rmtree")
@mock.patch("deepfellow.infra.prune.run")
@mock.patch("deepfellow.infra.prune.echo")
@mock.patch("deepfellow.infra.prune.assert_docker")
@mock.patch("deepfellow.infra.prune.check_infra_directory")
def test_prune_tears_down_stack_and_removes_directory(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    directory: Path,
) -> None:
    prune(directory=directory)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(_DOWN_COMMAND, directory, quiet=True)
    assert mock_rmtree.call_count == 1
    assert mock_rmtree.call_args == mock.call(directory)
    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == mock.call("DeepFellow Infra pruned.")


@mock.patch("deepfellow.infra.prune.rmtree")
@mock.patch("deepfellow.infra.prune.run")
@mock.patch("deepfellow.infra.prune.echo")
@mock.patch("deepfellow.infra.prune.assert_docker")
@mock.patch("deepfellow.infra.prune.check_infra_directory")
def test_prune_reports_progress_in_order(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    directory: Path,
) -> None:
    prune(directory=directory)

    assert mock_echo.info.call_args_list == [
        mock.call("Pruning DeepFellow Infra."),
        mock.call("Removing DeepFellow Infra containers and volumes."),
        mock.call("Removing DeepFellow Infra files."),
    ]
