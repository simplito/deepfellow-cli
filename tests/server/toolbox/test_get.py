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

from deepfellow.server.toolbox.get import get
from deepfellow.server.toolbox.utils import Toolbox


@mock.patch("deepfellow.server.toolbox.get.echo.info")
@mock.patch("deepfellow.server.toolbox.get.get_toolbox")
@mock.patch("deepfellow.server.toolbox.get.get_token")
@mock.patch("deepfellow.server.toolbox.get.get_server_url")
@mock.patch("deepfellow.server.toolbox.get.state")
def test_get_prints_toolbox_returned_by_get_toolbox(
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_toolbox: Mock,
    mock_info: Mock,
) -> None:
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    toolbox = Toolbox(id="toolbox-id", name="Toolbox Name", project_id="project-id", created_at=0)
    mock_get_toolbox.return_value = toolbox

    get(project_id="project-id", toolbox_id="toolbox-id", server=None, organization_id="org-id")

    assert mock_get_toolbox.call_count == 1
    assert mock_get_toolbox.call_args == mock.call("https://server", "token", "project-id", "org-id", "toolbox-id")
    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(str(toolbox))
