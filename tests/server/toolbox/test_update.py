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

from deepfellow.server.toolbox.update import update
from deepfellow.server.toolbox.utils import Toolbox


@mock.patch("deepfellow.server.toolbox.update.echo.info")
@mock.patch("deepfellow.server.toolbox.update.update_toolbox")
@mock.patch("deepfellow.server.toolbox.update.get_token")
@mock.patch("deepfellow.server.toolbox.update.get_server_url")
@mock.patch("deepfellow.server.toolbox.update.state")
def test_update_calls_update_toolbox_and_echoes_result(
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_update_toolbox: Mock,
    mock_info: Mock,
) -> None:
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    toolbox = Toolbox(id="toolbox-id", name="Renamed", project_id="project-id", created_at=0)
    mock_update_toolbox.return_value = toolbox

    update(
        project_id="project-id",
        toolbox_id="toolbox-id",
        name="Renamed",
        server=None,
        organization_id="org-id",
    )

    assert mock_update_toolbox.call_count == 1
    assert mock_update_toolbox.call_args == mock.call(
        "https://server", "token", "project-id", "org-id", "toolbox-id", "Renamed"
    )
    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(str(toolbox))
