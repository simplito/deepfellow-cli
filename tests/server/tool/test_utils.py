# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from io import StringIO
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.server.tool.utils import (
    Tool,
    create_tool,
    delete_tool,
    get_tool,
    list_tools,
    read_json_body,
    update_tool,
)


def tool_data() -> dict[str, Any]:
    return {
        "id": "tool-id",
        "definition": {"type": "mcp", "server_label": "git mcp", "server_url": "http://127.0.0.1:8001/mcp"},
        "toolbox_id": "toolbox-id",
        "created_at": 0,
    }


@mock.patch("deepfellow.server.tool.utils.datetime_to_str")
def test_created_at_to_str_returns_formatted_date(mock_datetime_to_str: Mock):
    mock_datetime_to_str.return_value = "2026-07-31"
    tool = Tool(**tool_data())

    result: str = tool.created_at_to_str()

    assert result == "2026-07-31"
    assert mock_datetime_to_str.call_count == 1
    assert mock_datetime_to_str.call_args == mock.call(tool.created_at)


def test_as_dict_returns_all_fields_with_serialized_definition() -> None:
    tool = Tool(**tool_data())

    result: dict[str, Any] = tool.as_dict()

    assert result["id"] == "tool-id"
    assert result["toolbox_id"] == "toolbox-id"
    assert json.loads(result["definition"]) == tool_data()["definition"]


def test_str_includes_all_as_dict_entries() -> None:
    tool = Tool(**tool_data())

    result: str = str(tool)

    for key, value in tool.as_dict().items():
        assert f"{key}: {value}" in result


def test_read_json_body_reads_from_config_file(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text('{"type": "mcp"}')

    result = read_json_body(config)

    assert result == {"type": "mcp"}


@mock.patch("deepfellow.server.tool.utils.sys.stdin", new_callable=StringIO)
def test_read_json_body_reads_from_stdin_when_no_config(mock_stdin: StringIO) -> None:
    mock_stdin.write('{"type": "mcp"}')
    mock_stdin.seek(0)
    mock_stdin.isatty = lambda: False  # type: ignore[method-assign]

    result = read_json_body(None)

    assert result == {"type": "mcp"}


@mock.patch("deepfellow.server.tool.utils.sys.stdin")
def test_read_json_body_exits_when_no_config_and_stdin_is_a_tty(mock_stdin: Mock) -> None:
    mock_stdin.isatty.return_value = True

    with pytest.raises(typer.Exit) as exc_info:
        read_json_body(None)

    assert exc_info.value.exit_code == 1


def test_read_json_body_exits_on_invalid_json(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text("not json")

    with pytest.raises(typer.Exit) as exc_info:
        read_json_body(config)

    assert exc_info.value.exit_code == 1


def test_read_json_body_exits_when_body_is_not_an_object(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text("[1, 2, 3]")

    with pytest.raises(typer.Exit) as exc_info:
        read_json_body(config)

    assert exc_info.value.exit_code == 1


@mock.patch("deepfellow.server.tool.utils.post")
def test_create_tool_returns_tool(mock_post: Mock):
    mock_post.return_value = tool_data()
    definition = {"type": "mcp", "server_label": "git mcp", "server_url": "http://127.0.0.1:8001/mcp"}

    result: Tool = create_tool("https://server", "token", "project-id", "org-id", "toolbox-id", definition)

    assert isinstance(result, Tool)
    assert result.id == "tool-id"
    assert mock_post.call_count == 1
    assert mock_post.call_args == mock.call(
        "https://server/toolboxes/toolbox-id/tools",
        "token",
        item_name="Tool",
        headers={"OpenAI-Project": "project-id", "OpenAI-Organization": "org-id"},
        data=definition,
    )


@mock.patch("deepfellow.server.tool.utils.get")
def test_list_tools_returns_tool_list(mock_get: Mock):
    mock_get.return_value = {"data": [tool_data()]}

    result: list[Tool] = list_tools("https://server", "token", "project-id", "org-id", "toolbox-id")

    assert len(result) == 1
    assert isinstance(result[0], Tool)
    assert result[0].id == "tool-id"
    assert mock_get.call_count == 1
    assert mock_get.call_args == mock.call(
        "https://server/toolboxes/toolbox-id/tools?limit=100",
        "token",
        item_name="Tools",
        headers={"OpenAI-Project": "project-id", "OpenAI-Organization": "org-id"},
    )


@mock.patch("deepfellow.server.tool.utils.get")
def test_list_tools_includes_pagination_params(mock_get: Mock):
    mock_get.return_value = {"data": []}

    list_tools(
        "https://server", "token", "project-id", None, "toolbox-id", limit=50, after="after-id", before="before-id"
    )

    assert mock_get.call_args == mock.call(
        "https://server/toolboxes/toolbox-id/tools?limit=50&after=after-id&before=before-id",
        "token",
        item_name="Tools",
        headers={"OpenAI-Project": "project-id"},
    )


@mock.patch("deepfellow.server.tool.utils.get")
def test_get_tool_returns_tool(mock_get: Mock):
    mock_get.return_value = tool_data()

    result: Tool = get_tool("https://server", "token", "project-id", "org-id", "toolbox-id", "tool-id")

    assert isinstance(result, Tool)
    assert result.id == "tool-id"
    assert mock_get.call_count == 1
    assert mock_get.call_args == mock.call(
        "https://server/toolboxes/toolbox-id/tools/tool-id",
        "token",
        item_name="Tool",
        headers={"OpenAI-Project": "project-id", "OpenAI-Organization": "org-id"},
    )


@mock.patch("deepfellow.server.tool.utils.make_request")
def test_update_tool_returns_updated_tool(mock_make_request: Mock):
    mock_make_request.return_value = tool_data()

    result: Tool = update_tool(
        "https://server", "token", "project-id", "org-id", "toolbox-id", "tool-id", {"server_description": "updated"}
    )

    assert isinstance(result, Tool)
    assert result.id == "tool-id"
    assert mock_make_request.call_count == 1
    assert mock_make_request.call_args == mock.call(
        "POST",
        "https://server/toolboxes/toolbox-id/tools/tool-id",
        "token",
        headers={"OpenAI-Project": "project-id", "OpenAI-Organization": "org-id"},
        data={"server_description": "updated"},
        err_msg="Unable to update tool.",
    )


@mock.patch("deepfellow.server.tool.utils.delete")
def test_delete_tool_calls_delete(mock_delete: Mock):
    delete_tool("https://server", "token", "project-id", "org-id", "toolbox-id", "tool-id")

    assert mock_delete.call_count == 1
    assert mock_delete.call_args == mock.call(
        "https://server/toolboxes/toolbox-id/tools/tool-id",
        "token",
        item_name="Tool",
        headers={"OpenAI-Project": "project-id", "OpenAI-Organization": "org-id"},
    )
