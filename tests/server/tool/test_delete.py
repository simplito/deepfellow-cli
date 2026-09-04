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

import pytest
import typer

from deepfellow.server.tool.delete import delete
from deepfellow.server.tool.utils import Tool


@pytest.fixture
def tool() -> Tool:
    return Tool(id="tool-id", definition={"type": "mcp"}, toolbox_id="toolbox-id", created_at=0)


@mock.patch("deepfellow.server.tool.delete.state")
@mock.patch("deepfellow.server.tool.delete.echo.debug")
@mock.patch("deepfellow.server.tool.delete.echo.success")
@mock.patch("deepfellow.server.tool.delete.echo.confirm")
@mock.patch("deepfellow.server.tool.delete.delete_tool")
@mock.patch("deepfellow.server.tool.delete.get_tool")
@mock.patch("deepfellow.server.tool.delete.get_token")
@mock.patch("deepfellow.server.tool.delete.get_server_url")
def test_delete_calls_delete_tool_when_confirmed(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_tool: Mock,
    mock_delete_tool: Mock,
    mock_confirm: Mock,
    mock_success: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    tool: Tool,
) -> None:
    mock_state.yes = False
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_tool.return_value = tool
    mock_confirm.return_value = True

    delete(project_id="project-id", toolbox_id="toolbox-id", tool_id="tool-id", server=None, organization_id="org-id")

    assert mock_delete_tool.call_count == 1
    assert mock_delete_tool.call_args == mock.call(
        "https://server", "token", "project-id", "org-id", "toolbox-id", "tool-id"
    )
    assert mock_success.call_args == mock.call(f"Tool '{tool.id}' deleted.")


@mock.patch("deepfellow.server.tool.delete.state")
@mock.patch("deepfellow.server.tool.delete.echo.debug")
@mock.patch("deepfellow.server.tool.delete.echo.success")
@mock.patch("deepfellow.server.tool.delete.echo.confirm")
@mock.patch("deepfellow.server.tool.delete.delete_tool")
@mock.patch("deepfellow.server.tool.delete.get_tool")
@mock.patch("deepfellow.server.tool.delete.get_token")
@mock.patch("deepfellow.server.tool.delete.get_server_url")
def test_delete_raises_exit_when_declined(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_tool: Mock,
    mock_delete_tool: Mock,
    mock_confirm: Mock,
    mock_success: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    tool: Tool,
) -> None:
    mock_state.yes = False
    mock_get_tool.return_value = tool
    mock_confirm.return_value = False

    with pytest.raises(typer.Exit) as exc_info:
        delete(
            project_id="project-id", toolbox_id="toolbox-id", tool_id="tool-id", server=None, organization_id="org-id"
        )

    assert exc_info.value.exit_code == 1
    assert mock_delete_tool.call_count == 0


@mock.patch("deepfellow.server.tool.delete.state")
@mock.patch("deepfellow.server.tool.delete.echo.debug")
@mock.patch("deepfellow.server.tool.delete.echo.success")
@mock.patch("deepfellow.server.tool.delete.echo.confirm")
@mock.patch("deepfellow.server.tool.delete.delete_tool")
@mock.patch("deepfellow.server.tool.delete.get_tool")
@mock.patch("deepfellow.server.tool.delete.get_token")
@mock.patch("deepfellow.server.tool.delete.get_server_url")
def test_delete_skips_confirm_prompt_when_yes(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_tool: Mock,
    mock_delete_tool: Mock,
    mock_confirm: Mock,
    mock_success: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    tool: Tool,
) -> None:
    mock_state.yes = True
    mock_get_tool.return_value = tool

    delete(project_id="project-id", toolbox_id="toolbox-id", tool_id="tool-id", server=None, organization_id="org-id")

    assert mock_confirm.call_count == 0
    assert mock_delete_tool.call_count == 1
    assert mock_debug.call_count == 1
    assert mock_debug.call_args == mock.call("Automatically confirming the delete.")
