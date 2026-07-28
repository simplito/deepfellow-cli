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

from deepfellow.server.utils.workspace import create_workspace


@mock.patch("deepfellow.server.utils.workspace.post")
def test_create_workspace_calls_post_with_expected_payload(mock_post: Mock) -> None:
    mock_post.return_value = {
        "organization": {"id": "org-id", "created_at": 0.0, "name": "Workspace", "owner_id": "owner-id"},
        "project": {
            "id": "project-id",
            "name": "Default",
            "status": "active",
            "models": [],
            "custom_endpoints": "all",
            "mcp_prefixes": "all",
            "created_at": 0.0,
        },
        "api_key": {
            "id": "key-id",
            "object": "organization.project.api_key",
            "name": "app",
            "redacted_value": "dfproj_....abc",
            "created_at": 0.0,
            "last_used_at": 0.0,
            "value": "dfproj_secret",
        },
    }

    workspace = create_workspace("https://server", "token", "Workspace", "Default", "app")

    assert mock_post.call_count == 1
    assert mock_post.call_args == mock.call(
        "https://server/admin/workspace/",
        "token",
        item_name="Workspace",
        data={"organization_name": "Workspace", "project_name": "Default", "api_key_name": "app"},
    )
    assert workspace.organization.id == "org-id"
    assert workspace.project.id == "project-id"
    assert workspace.api_key.value == "dfproj_secret"


@mock.patch("deepfellow.server.utils.workspace.post")
def test_create_workspace_str_includes_all_three_resources(mock_post: Mock) -> None:
    mock_post.return_value = {
        "organization": {"id": "org-id", "created_at": 0.0, "name": "Workspace", "owner_id": "owner-id"},
        "project": {
            "id": "project-id",
            "name": "Default",
            "status": "active",
            "models": [],
            "custom_endpoints": "all",
            "mcp_prefixes": "all",
            "created_at": 0.0,
        },
        "api_key": {
            "id": "key-id",
            "object": "organization.project.api_key",
            "name": "app",
            "redacted_value": "dfproj_....abc",
            "created_at": 0.0,
            "last_used_at": 0.0,
            "value": "dfproj_secret",
        },
    }

    workspace = create_workspace("https://server", "token", "Workspace", "Default", "app")
    result = str(workspace)

    assert "org-id" in result
    assert "project-id" in result
    assert "dfproj_secret" in result
