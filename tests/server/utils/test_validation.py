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

from deepfellow.server.utils.validation import check_server_directory


@mock.patch("deepfellow.server.utils.validation.check_service_directory")
def test_check_server_directory_delegates_to_check_service_directory(
    mock_check_service_directory: mock.MagicMock,
) -> None:
    directory = Path("/some/server/dir")

    check_server_directory(directory)

    assert mock_check_service_directory.call_count == 1
    assert mock_check_service_directory.call_args == mock.call(directory, "Server")
