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

from deepfellow.infra.mcp.uninstall import uninstall as uninstall_command
from deepfellow.infra.utils.mcp import uninstall


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_uninstall_deletes_model_instance_by_name(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock
) -> None:
    mock_make_request.return_value = {"status": "OK"}

    uninstall(name="duckduckgo", server=None)

    assert mock_make_request.call_count == 1
    assert mock_make_request.call_args == mock.call(
        method="DELETE",
        url="http://infra:8086/admin/services/mcp/models/_?model_id=duckduckgo",
        token="test-key",
        data={"purge": False},
        err_msg="Unable to uninstall MCP server.",
        reraise=True,
    )
    assert mock_env_set.call_count == 2
    assert all(call.kwargs.get("quiet") is True for call in mock_env_set.call_args_list)


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_uninstall_forwards_purge_flag(mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock) -> None:
    mock_make_request.return_value = {"status": "OK"}

    uninstall(name="my-server", server=None, purge=True)

    assert mock_make_request.call_args == mock.call(
        method="DELETE",
        url="http://infra:8086/admin/services/mcp/models/_?model_id=my-server",
        token="test-key",
        data={"purge": True},
        err_msg="Unable to uninstall MCP server.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_uninstall_percent_encodes_name_with_query_string_characters(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock
) -> None:
    mock_make_request.return_value = {"status": "OK"}

    uninstall(name="x&model_id=duckduckgo", server=None)

    assert mock_make_request.call_args == mock.call(
        method="DELETE",
        url="http://infra:8086/admin/services/mcp/models/_?model_id=x%26model_id%3Dduckduckgo",
        token="test-key",
        data={"purge": False},
        err_msg="Unable to uninstall MCP server.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.utils.mcp.echo.error")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_uninstall_exits_when_status_not_ok(mock_resolve: Mock, mock_make_request: Mock, mock_error: Mock) -> None:
    mock_make_request.return_value = {"status": "ERROR"}

    with pytest.raises(typer.Exit):
        uninstall(name="unknown", server=None)

    assert mock_error.call_count == 1
    assert mock_error.call_args == mock.call("Unable to uninstall MCP server.")


@mock.patch("deepfellow.infra.mcp.uninstall.echo.success")
@mock.patch("deepfellow.infra.mcp.uninstall.uninstall_util")
def test_uninstall_command_delegates_to_uninstall_util(mock_uninstall_util: Mock, mock_success: Mock) -> None:
    uninstall_command(name="my-server", server="http://infra:8086", purge=True)

    assert mock_uninstall_util.call_count == 1
    assert mock_uninstall_util.call_args == mock.call(name="my-server", server="http://infra:8086", purge=True)
    assert mock_success.call_count == 1
