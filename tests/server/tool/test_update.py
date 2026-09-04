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

from deepfellow.server.tool.update import update
from deepfellow.server.tool.utils import Tool


@mock.patch("deepfellow.server.tool.update.echo.info")
@mock.patch("deepfellow.server.tool.update.update_tool")
@mock.patch("deepfellow.server.tool.update.get_token")
@mock.patch("deepfellow.server.tool.update.get_server_url")
@mock.patch("deepfellow.server.tool.update.state")
@mock.patch("deepfellow.server.tool.update.read_json_body")
def test_update_calls_update_tool_with_parsed_body_and_echoes_result(
    mock_read_json_body: Mock,
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_update_tool: Mock,
    mock_info: Mock,
) -> None:
    update_body = {"server_description": "updated"}
    mock_read_json_body.return_value = update_body
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    tool = Tool(id="tool-id", definition={"type": "mcp"}, toolbox_id="toolbox-id", created_at=0)
    mock_update_tool.return_value = tool

    update(
        project_id="project-id",
        toolbox_id="toolbox-id",
        tool_id="tool-id",
        server=None,
        organization_id="org-id",
        config=None,
    )

    assert mock_read_json_body.call_count == 1
    assert mock_read_json_body.call_args == mock.call(None, what="tool update")
    assert mock_update_tool.call_count == 1
    assert mock_update_tool.call_args == mock.call(
        "https://server", "token", "project-id", "org-id", "toolbox-id", "tool-id", update_body
    )
    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(str(tool))


@mock.patch("deepfellow.server.tool.update.echo.info")
@mock.patch("deepfellow.server.tool.update.update_tool")
@mock.patch("deepfellow.server.tool.update.get_token")
@mock.patch("deepfellow.server.tool.update.get_server_url")
@mock.patch("deepfellow.server.tool.update.state")
@mock.patch("deepfellow.server.tool.update.read_json_body")
def test_update_passes_config_path_through_to_read_json_body(
    mock_read_json_body: Mock,
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_update_tool: Mock,
    mock_info: Mock,
) -> None:
    mock_read_json_body.return_value = {}
    mock_update_tool.return_value = Tool(
        id="tool-id", definition={"type": "mcp"}, toolbox_id="toolbox-id", created_at=0
    )
    config_path = Path("/update.json")

    update(
        project_id="project-id",
        toolbox_id="toolbox-id",
        tool_id="tool-id",
        server=None,
        organization_id="org-id",
        config=config_path,
    )

    assert mock_read_json_body.call_args == mock.call(config_path, what="tool update")
