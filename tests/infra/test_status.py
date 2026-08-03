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

from deepfellow.infra.status import status


@mock.patch("deepfellow.infra.status.print_docker_status")
@mock.patch("deepfellow.infra.status.echo.debug")
@mock.patch("deepfellow.infra.status.assert_docker")
def test_status_checks_docker_before_printing_status(
    mock_assert_docker: Mock,
    mock_echo_debug: Mock,
    mock_print_docker_status: Mock,
    directory: Path,
) -> None:
    status(directory=directory)

    assert mock_assert_docker.call_count == 1
    assert mock_assert_docker.call_args == mock.call()


@mock.patch("deepfellow.infra.status.print_docker_status")
@mock.patch("deepfellow.infra.status.echo.debug")
@mock.patch("deepfellow.infra.status.assert_docker")
def test_status_prints_docker_status_for_infra_context(
    mock_assert_docker: Mock,
    mock_echo_debug: Mock,
    mock_print_docker_status: Mock,
    directory: Path,
) -> None:
    status(directory=directory)

    assert mock_print_docker_status.call_count == 1
    assert mock_print_docker_status.call_args == mock.call(directory, "infra")


@mock.patch("deepfellow.infra.status.print_docker_status")
@mock.patch("deepfellow.infra.status.echo.debug")
@mock.patch("deepfellow.infra.status.assert_docker")
def test_status_logs_debug_message(
    mock_assert_docker: Mock,
    mock_echo_debug: Mock,
    mock_print_docker_status: Mock,
    directory: Path,
) -> None:
    status(directory=directory)

    assert mock_echo_debug.call_count == 1
    assert mock_echo_debug.call_args == mock.call("Showing DeepFellow Infra status")
