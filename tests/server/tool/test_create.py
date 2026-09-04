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

from deepfellow.server.tool.create import create
from deepfellow.server.tool.utils import Tool


def _tool() -> Tool:
    return Tool(
        id="tool-id",
        definition={"type": "mcp", "server_label": "git mcp", "server_url": "http://127.0.0.1:8001/mcp"},
        toolbox_id="toolbox-id",
        created_at=0,
    )


@mock.patch("deepfellow.server.tool.create.echo.info")
@mock.patch("deepfellow.server.tool.create.create_tool")
@mock.patch("deepfellow.server.tool.create.get_token")
@mock.patch("deepfellow.server.tool.create.get_server_url")
@mock.patch("deepfellow.server.tool.create.state")
@mock.patch("deepfellow.server.tool.create.read_json_body")
def test_create_calls_create_tool_with_parsed_definition_and_echoes_result(
    mock_read_json_body: Mock,
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_create_tool: Mock,
    mock_info: Mock,
) -> None:
    definition = {"type": "mcp", "server_label": "git mcp", "server_url": "http://127.0.0.1:8001/mcp"}
    mock_read_json_body.return_value = definition
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    tool = _tool()
    mock_create_tool.return_value = tool

    create(project_id="project-id", toolbox_id="toolbox-id", server=None, organization_id="org-id", config=None)

    assert mock_read_json_body.call_count == 1
    assert mock_read_json_body.call_args == mock.call(None)
    assert mock_create_tool.call_count == 1
    assert mock_create_tool.call_args == mock.call(
        "https://server", "token", "project-id", "org-id", "toolbox-id", definition
    )
    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(str(tool))


@mock.patch("deepfellow.server.tool.create.echo.info")
@mock.patch("deepfellow.server.tool.create.create_tool")
@mock.patch("deepfellow.server.tool.create.get_token")
@mock.patch("deepfellow.server.tool.create.get_server_url")
@mock.patch("deepfellow.server.tool.create.state")
@mock.patch("deepfellow.server.tool.create.read_json_body")
def test_create_passes_config_path_through_to_read_json_body(
    mock_read_json_body: Mock,
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_create_tool: Mock,
    mock_info: Mock,
) -> None:
    mock_read_json_body.return_value = {"type": "mcp"}
    mock_create_tool.return_value = _tool()
    config_path = Path("/config.json")

    create(project_id="project-id", toolbox_id="toolbox-id", server=None, organization_id="org-id", config=config_path)

    assert mock_read_json_body.call_args == mock.call(config_path)
