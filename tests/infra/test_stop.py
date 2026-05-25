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

import pytest

from deepfellow.infra.stop import stop


@pytest.fixture
def run_args() -> list:
    return ["docker", "compose", "down"]


@mock.patch("deepfellow.infra.stop.run")
@mock.patch("deepfellow.infra.stop.echo.success")
@mock.patch("deepfellow.infra.stop.echo.debug")
@mock.patch("deepfellow.infra.stop.check_infra_directory")
def test_stop_success(
    mock_check: Mock,
    mock_echo_debug: Mock,
    mock_echo_success: Mock,
    mock_run: Mock,
    directory: Path,
    run_args: list,
) -> None:
    stop(directory=directory)

    assert mock_check.call_count == 1
    assert mock_check.call_args == ((directory,), {})
    assert mock_run.call_count == 1
    assert mock_run.call_args == ((run_args,), {"cwd": directory})
    assert mock_echo_debug.call_count == 1
    assert mock_echo_debug.call_args == mock.call("Stopping DeepFellow Infra")
    assert mock_echo_success.call_args == mock.call("DeepFellow Infra is down")
