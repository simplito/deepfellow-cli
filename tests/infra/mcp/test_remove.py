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

from deepfellow.infra.mcp.remove import remove as remove_command
from deepfellow.infra.utils.mcp import McpServer, remove


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp._list")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_remove_deletes_resolved_custom_model(
    mock_resolve: Mock, mock_list: Mock, mock_make_request: Mock, mock_env_set: Mock
) -> None:
    mock_list.return_value = [
        McpServer(id="other-server", kind="mcp", installed=True, custom_model_id="cm-0"),
        McpServer(id="my-server", kind="mcp", installed=True, custom_model_id="cm-1"),
    ]
    mock_make_request.return_value = {"status": "OK"}

    remove(name="my-server", server=None)

    assert mock_list.call_args == mock.call("http://infra:8086", "test-key", quiet=True)
    assert mock_make_request.call_count == 1
    assert mock_make_request.call_args == mock.call(
        method="DELETE",
        url="http://infra:8086/admin/services/mcp/models/custom/cm-1",
        token="test-key",
        err_msg="Unable to remove MCP server.",
        reraise=True,
    )
    assert mock_env_set.call_count == 2
    assert all(call.kwargs.get("quiet") is True for call in mock_env_set.call_args_list)


@mock.patch("deepfellow.infra.utils.mcp.echo.error")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp._list")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_remove_exits_when_status_not_ok(
    mock_resolve: Mock, mock_list: Mock, mock_make_request: Mock, mock_error: Mock
) -> None:
    mock_list.return_value = [McpServer(id="my-server", kind="mcp", installed=True, custom_model_id="cm-1")]
    mock_make_request.return_value = {"status": "ERROR"}

    with pytest.raises(typer.Exit):
        remove(name="my-server", server=None)

    assert mock_error.call_count == 1
    assert mock_error.call_args == mock.call("Unable to remove MCP server.")


@mock.patch("deepfellow.infra.utils.mcp.echo.error")
@mock.patch("deepfellow.infra.utils.mcp._list")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_remove_exits_when_not_found(mock_resolve: Mock, mock_list: Mock, mock_error: Mock) -> None:
    mock_list.return_value = []

    with pytest.raises(typer.Exit):
        remove(name="unknown", server=None)

    assert mock_error.call_count == 1
    assert mock_error.call_args == mock.call("MCP server 'unknown' not found.")


@mock.patch("deepfellow.infra.utils.mcp.echo.error")
@mock.patch("deepfellow.infra.utils.mcp._list")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_remove_exits_when_not_custom(mock_resolve: Mock, mock_list: Mock, mock_error: Mock) -> None:
    mock_list.return_value = [McpServer(id="builtin", kind="mcp", installed=True, custom_model_id=None)]

    with pytest.raises(typer.Exit):
        remove(name="builtin", server=None)

    assert mock_error.call_count == 1
    assert mock_error.call_args == mock.call(
        "MCP server 'builtin' is a built-in model and cannot be removed. Use `mcp uninstall builtin --purge` instead."
    )


@mock.patch("deepfellow.infra.mcp.remove.echo.success")
@mock.patch("deepfellow.infra.mcp.remove.remove_util")
def test_remove_command_delegates_to_remove_util(mock_remove_util: Mock, mock_success: Mock) -> None:
    remove_command(name="my-server", server="http://infra:8086")

    assert mock_remove_util.call_count == 1
    assert mock_remove_util.call_args == mock.call(name="my-server", server="http://infra:8086")
    assert mock_success.call_count == 1
