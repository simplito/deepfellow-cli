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

from deepfellow.server.stop import stop


@mock.patch("deepfellow.server.stop.run")
@mock.patch("deepfellow.server.stop.echo.success")
@mock.patch("deepfellow.server.stop.echo.debug")
@mock.patch("deepfellow.server.stop.check_server_directory")
def test_stop_stops_server(
    mock_check_server_directory: mock.MagicMock,
    mock_debug: mock.MagicMock,
    mock_success: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
) -> None:
    stop(directory=directory)

    assert mock_check_server_directory.call_count == 1
    assert mock_check_server_directory.call_args == mock.call(directory)
    assert mock_debug.call_count == 1
    assert mock_debug.call_args == mock.call("Stopping DeepFellow Server")
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "down"], cwd=directory)
    assert mock_success.call_count == 1
    assert mock_success.call_args == mock.call("DeepFellow Server is down")
