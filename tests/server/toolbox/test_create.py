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

from deepfellow.server.toolbox.create import create
from deepfellow.server.toolbox.utils import Toolbox


def _toolbox() -> Toolbox:
    return Toolbox(id="toolbox-id", name="Toolbox Name", project_id="project-id", created_at=0)


@mock.patch("deepfellow.server.toolbox.create.echo.info")
@mock.patch("deepfellow.server.toolbox.create.create_toolbox")
@mock.patch("deepfellow.server.toolbox.create.get_token")
@mock.patch("deepfellow.server.toolbox.create.get_server_url")
@mock.patch("deepfellow.server.toolbox.create.state")
def test_create_calls_create_toolbox_and_echoes_result(
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_create_toolbox: Mock,
    mock_info: Mock,
) -> None:
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    toolbox = _toolbox()
    mock_create_toolbox.return_value = toolbox

    create(project_id="project-id", name="Toolbox Name", server=None, organization_id="org-id")

    assert mock_get_token.call_count == 1
    assert mock_get_token.call_args == mock.call("secrets-file", "https://server")
    assert mock_create_toolbox.call_count == 1
    assert mock_create_toolbox.call_args == mock.call("https://server", "token", "project-id", "org-id", "Toolbox Name")
    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(str(toolbox))
