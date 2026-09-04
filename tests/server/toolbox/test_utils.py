# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any
from unittest import mock
from unittest.mock import Mock

from deepfellow.server.toolbox.utils import (
    Toolbox,
    create_toolbox,
    delete_toolbox,
    get_toolbox,
    list_toolboxes,
    update_toolbox,
)


def toolbox_data() -> dict[str, Any]:
    return {
        "id": "toolbox-id",
        "name": "Toolbox Name",
        "project_id": "project-id",
        "created_at": 0,
    }


@mock.patch("deepfellow.server.toolbox.utils.datetime_to_str")
def test_created_at_to_str_returns_formatted_date(mock_datetime_to_str: Mock):
    mock_datetime_to_str.return_value = "2026-07-31"
    toolbox = Toolbox(**toolbox_data())

    result: str = toolbox.created_at_to_str()

    assert result == "2026-07-31"
    assert mock_datetime_to_str.call_count == 1
    assert mock_datetime_to_str.call_args == mock.call(toolbox.created_at)


def test_as_dict_returns_all_fields() -> None:
    toolbox = Toolbox(**toolbox_data())

    result: dict[str, str] = toolbox.as_dict()

    assert result["id"] == "toolbox-id"
    assert result["name"] == "Toolbox Name"
    assert result["project_id"] == "project-id"


def test_str_joins_as_dict_items_as_lines() -> None:
    toolbox = Toolbox(**toolbox_data())

    result: str = str(toolbox)

    for key, value in toolbox.as_dict().items():
        assert f"{key}: {value}" in result.splitlines()


@mock.patch("deepfellow.server.toolbox.utils.post")
def test_create_toolbox_returns_toolbox(mock_post: Mock):
    mock_post.return_value = toolbox_data()

    result: Toolbox = create_toolbox("https://server", "token", "project-id", "org-id", "Toolbox Name")

    assert isinstance(result, Toolbox)
    assert result.id == "toolbox-id"
    assert mock_post.call_count == 1
    assert mock_post.call_args == mock.call(
        "https://server/toolboxes",
        "token",
        item_name="Toolbox",
        headers={"OpenAI-Project": "project-id", "OpenAI-Organization": "org-id"},
        data={"name": "Toolbox Name"},
    )


@mock.patch("deepfellow.server.toolbox.utils.post")
def test_create_toolbox_omits_organization_header_when_none(mock_post: Mock):
    mock_post.return_value = toolbox_data()

    create_toolbox("https://server", "token", "project-id", None, "Toolbox Name")

    assert mock_post.call_args == mock.call(
        "https://server/toolboxes",
        "token",
        item_name="Toolbox",
        headers={"OpenAI-Project": "project-id"},
        data={"name": "Toolbox Name"},
    )


@mock.patch("deepfellow.server.toolbox.utils.get")
def test_list_toolboxes_returns_toolbox_list(mock_get: Mock):
    mock_get.return_value = {"data": [toolbox_data()]}

    result: list[Toolbox] = list_toolboxes("https://server", "token", "project-id", "org-id")

    assert len(result) == 1
    assert isinstance(result[0], Toolbox)
    assert result[0].id == "toolbox-id"
    assert mock_get.call_count == 1
    assert mock_get.call_args == mock.call(
        "https://server/toolboxes?limit=100",
        "token",
        item_name="Toolboxes",
        headers={"OpenAI-Project": "project-id", "OpenAI-Organization": "org-id"},
    )


@mock.patch("deepfellow.server.toolbox.utils.get")
def test_list_toolboxes_includes_pagination_params(mock_get: Mock):
    mock_get.return_value = {"data": []}

    list_toolboxes("https://server", "token", "project-id", None, limit=50, after="after-id", before="before-id")

    assert mock_get.call_args == mock.call(
        "https://server/toolboxes?limit=50&after=after-id&before=before-id",
        "token",
        item_name="Toolboxes",
        headers={"OpenAI-Project": "project-id"},
    )


@mock.patch("deepfellow.server.toolbox.utils.get")
def test_get_toolbox_returns_toolbox(mock_get: Mock):
    mock_get.return_value = toolbox_data()

    result: Toolbox = get_toolbox("https://server", "token", "project-id", "org-id", "toolbox-id")

    assert isinstance(result, Toolbox)
    assert result.id == "toolbox-id"
    assert mock_get.call_count == 1
    assert mock_get.call_args == mock.call(
        "https://server/toolboxes/toolbox-id",
        "token",
        item_name="Toolbox",
        headers={"OpenAI-Project": "project-id", "OpenAI-Organization": "org-id"},
    )


@mock.patch("deepfellow.server.toolbox.utils.make_request")
def test_update_toolbox_returns_updated_toolbox(mock_make_request: Mock):
    data = toolbox_data()
    data["name"] = "Renamed"
    mock_make_request.return_value = data

    result: Toolbox = update_toolbox("https://server", "token", "project-id", "org-id", "toolbox-id", "Renamed")

    assert isinstance(result, Toolbox)
    assert result.name == "Renamed"
    assert mock_make_request.call_count == 1
    assert mock_make_request.call_args == mock.call(
        "POST",
        "https://server/toolboxes/toolbox-id",
        "token",
        headers={"OpenAI-Project": "project-id", "OpenAI-Organization": "org-id"},
        data={"name": "Renamed"},
        err_msg="Unable to update toolbox.",
    )


@mock.patch("deepfellow.server.toolbox.utils.delete")
def test_delete_toolbox_calls_delete(mock_delete: Mock):
    delete_toolbox("https://server", "token", "project-id", "org-id", "toolbox-id")

    assert mock_delete.call_count == 1
    assert mock_delete.call_args == mock.call(
        "https://server/toolboxes/toolbox-id",
        "token",
        item_name="Toolbox",
        headers={"OpenAI-Project": "project-id", "OpenAI-Organization": "org-id"},
    )
