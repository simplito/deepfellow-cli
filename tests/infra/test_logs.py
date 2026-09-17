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

from deepfellow.infra.logs import logs


@mock.patch("deepfellow.infra.logs.run")
@mock.patch("deepfellow.infra.logs.echo.info")
@mock.patch("deepfellow.infra.logs.assert_docker")
def test_logs_runs_docker_compose_logs_with_default_tail(
    mock_assert_docker: mock.MagicMock,
    mock_info: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
) -> None:
    logs(directory=directory, follow=False, tail=20)

    assert mock_assert_docker.call_count == 1
    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call("Showing DeepFellow Infra logs")
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "logs", "infra", "--tail", "20"], cwd=directory)


@mock.patch("deepfellow.infra.logs.run")
@mock.patch("deepfellow.infra.logs.echo.info")
@mock.patch("deepfellow.infra.logs.assert_docker")
def test_logs_appends_follow_flag_when_follow_is_true(
    mock_assert_docker: mock.MagicMock,
    mock_info: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
) -> None:
    logs(directory=directory, follow=True, tail=20)

    assert mock_assert_docker.call_count == 1
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "logs", "infra", "-f", "--tail", "20"], cwd=directory)


@mock.patch("deepfellow.infra.logs.run")
@mock.patch("deepfellow.infra.logs.echo.info")
@mock.patch("deepfellow.infra.logs.assert_docker")
def test_logs_omits_follow_flag_when_follow_is_false(
    mock_assert_docker: mock.MagicMock,
    mock_info: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
) -> None:
    logs(directory=directory, follow=False, tail=50)

    assert mock_assert_docker.call_count == 1
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "logs", "infra", "--tail", "50"], cwd=directory)


@mock.patch("deepfellow.infra.logs.run")
@mock.patch("deepfellow.infra.logs.echo.info")
@mock.patch("deepfellow.infra.logs.assert_docker")
def test_logs_omits_tail_flag_when_tail_is_none(
    mock_assert_docker: mock.MagicMock,
    mock_info: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
) -> None:
    logs(directory=directory, follow=False, tail=None)

    assert mock_assert_docker.call_count == 1
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "logs", "infra"], cwd=directory)
