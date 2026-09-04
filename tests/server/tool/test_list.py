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

from deepfellow.server.tool.list import list
from deepfellow.server.tool.utils import Tool


def _tool(tool_id: str) -> Tool:
    return Tool(id=tool_id, definition={"type": "mcp"}, toolbox_id="toolbox-id", created_at=0)


@mock.patch("deepfellow.server.tool.list.echo.info")
@mock.patch("deepfellow.server.tool.list.list_tools")
@mock.patch("deepfellow.server.tool.list.get_token")
@mock.patch("deepfellow.server.tool.list.get_server_url")
@mock.patch("deepfellow.server.tool.list.state")
def test_list_prints_tools_joined_by_double_newline(
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_list_tools: Mock,
    mock_info: Mock,
) -> None:
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    tools = [_tool("tool-1"), _tool("tool-2")]
    mock_list_tools.return_value = tools

    list(
        project_id="project-id",
        toolbox_id="toolbox-id",
        server=None,
        organization_id="org-id",
        limit=100,
        after=None,
        before=None,
    )

    assert mock_list_tools.call_count == 1
    assert mock_list_tools.call_args == mock.call(
        "https://server", "token", "project-id", "org-id", "toolbox-id", limit=100, after=None, before=None
    )
    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(f"{tools[0]}\n\n{tools[1]}")


@mock.patch("deepfellow.server.tool.list.echo.info")
@mock.patch("deepfellow.server.tool.list.list_tools")
@mock.patch("deepfellow.server.tool.list.get_token")
@mock.patch("deepfellow.server.tool.list.get_server_url")
@mock.patch("deepfellow.server.tool.list.state")
def test_list_passes_after_and_before_to_list_tools(
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_list_tools: Mock,
    mock_info: Mock,
) -> None:
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_list_tools.return_value = []

    list(
        project_id="project-id",
        toolbox_id="toolbox-id",
        server=None,
        organization_id="org-id",
        limit=100,
        after="after-id",
        before="before-id",
    )

    assert mock_list_tools.call_args == mock.call(
        "https://server",
        "token",
        "project-id",
        "org-id",
        "toolbox-id",
        limit=100,
        after="after-id",
        before="before-id",
    )


@mock.patch("deepfellow.server.tool.list.echo.info")
@mock.patch("deepfellow.server.tool.list.list_tools")
@mock.patch("deepfellow.server.tool.list.get_token")
@mock.patch("deepfellow.server.tool.list.get_server_url")
@mock.patch("deepfellow.server.tool.list.state")
def test_list_prints_message_when_no_tools(
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_list_tools: Mock,
    mock_info: Mock,
) -> None:
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_list_tools.return_value = []

    list(project_id="project-id", toolbox_id="toolbox-id", server=None, organization_id="org-id", limit=100)

    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call("No tools found.")
