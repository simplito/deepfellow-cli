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

from deepfellow.server.project.utils import (
    Project,
    archive_project,
    create_project,
    get_project,
    list_projects,
    update_project,
)


def project_data() -> dict[str, Any]:
    return {
        "name": "Project Name",
        "id": "project-id",
        "status": "active",
        "models": ["model-a"],
        "custom_endpoints": ["endpoint-a"],
        "mcp_prefixes": ["prefix-a"],
        "created_at": 0.0,
    }


@mock.patch("deepfellow.server.project.utils.datetime_to_str")
def test_created_at_to_str_returns_formatted_date(mock_datetime_to_str: Mock):
    mock_datetime_to_str.return_value = "2026-07-31"
    project = Project(**project_data())

    result: str = project.created_at_to_str()

    assert result == "2026-07-31"
    assert mock_datetime_to_str.call_count == 1
    assert mock_datetime_to_str.call_args == mock.call(project.created_at)


def test_as_dict_returns_all_fields() -> None:
    project = Project(**project_data())

    result: dict[str, str | list[str] | None] = project.as_dict()

    assert result["name"] == "Project Name"
    assert result["id"] == "project-id"
    assert result["status"] == "active"
    assert result["models"] == ["model-a"]
    assert result["custom_endpoints"] == ["endpoint-a"]
    assert result["mcp_prefixes"] == ["prefix-a"]


def test_str_joins_as_dict_items_as_lines() -> None:
    project = Project(**project_data())

    result: str = str(project)

    for key, value in project.as_dict().items():
        assert f"{key}: {value}" in result.splitlines()


@mock.patch("deepfellow.server.project.utils.get")
def test_get_project_returns_project(mock_get: Mock):
    mock_get.return_value = project_data()

    result: Project = get_project("https://server", "token", "org-id", "project-id")

    assert isinstance(result, Project)
    assert result.id == "project-id"
    assert mock_get.call_count == 1
    assert mock_get.call_args == mock.call(
        "https://server/v1/organization/projects/project-id",
        "token",
        item_name="Project",
        headers={"OpenAI-Organization": "org-id"},
    )


@mock.patch("deepfellow.server.project.utils.get")
def test_list_projects_returns_project_list(mock_get: Mock):
    mock_get.return_value = {"data": [project_data()]}

    result: list[Project] = list_projects("https://server", "token", "org-id")

    assert len(result) == 1
    assert isinstance(result[0], Project)
    assert result[0].id == "project-id"
    assert mock_get.call_count == 1
    assert mock_get.call_args == mock.call(
        "https://server/v1/organization/projects",
        "token",
        item_name="Project",
        headers={"OpenAI-Organization": "org-id"},
    )


@mock.patch("deepfellow.server.project.utils.post")
def test_create_project_returns_project(mock_post: Mock):
    mock_post.return_value = project_data()

    result: Project = create_project("https://server", "token", "org-id", {"name": "Project Name"})

    assert isinstance(result, Project)
    assert result.name == "Project Name"
    assert mock_post.call_count == 1
    assert mock_post.call_args == mock.call(
        "https://server/v1/organization/projects",
        "token",
        item_name="Project",
        headers={"OpenAI-Organization": "org-id"},
        data={"name": "Project Name"},
    )


@mock.patch("deepfellow.server.project.utils.make_request")
def test_update_project_returns_updated_project(mock_make_request: Mock):
    data = project_data()
    data["models"] = ["model-a", "model-b"]
    mock_make_request.return_value = data

    result: Project = update_project(
        "https://server", "token", "org-id", "project-id", {"models": ["model-a", "model-b"]}
    )

    assert isinstance(result, Project)
    assert result.models == ["model-a", "model-b"]
    assert mock_make_request.call_count == 1
    assert mock_make_request.call_args == mock.call(
        "POST",
        "https://server/v1/organization/projects/project-id",
        "token",
        headers={"OpenAI-Organization": "org-id"},
        data={"models": ["model-a", "model-b"]},
        err_msg="Unable to update project.",
    )


@mock.patch("deepfellow.server.project.utils.post")
def test_archive_project_returns_archived_project(mock_post: Mock):
    data = project_data()
    data["status"] = "archived"
    mock_post.return_value = data

    result: Project = archive_project("https://server", "token", "org-id", "project-id")

    assert isinstance(result, Project)
    assert result.status == "archived"
    assert mock_post.call_count == 1
    assert mock_post.call_args == mock.call(
        "https://server/v1/organization/projects/project-id/archive",
        "token",
        item_name="Project",
        headers={"OpenAI-Organization": "org-id"},
    )
