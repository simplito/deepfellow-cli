# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utils for the project commands."""

from dataclasses import dataclass
from typing import Any, Literal

from deepfellow.common.rest import get, post
from deepfellow.server.utils.time import datetime_to_str


@dataclass
class Project:
    name: str
    id: str
    status: Literal["active", "archived"]
    models: list[str] | str
    custom_endpoints: list[str]
    created_at: float

    def created_at_to_str(self) -> str:
        """Convert created_at to a localized date string."""
        return datetime_to_str(self.created_at)

    def as_dict(self) -> dict[str, str | list[str]]:
        """Dictionary representation of Organization."""
        return {
            "name": self.name,
            "id": self.id,
            "status": self.status,
            "created_at": self.created_at_to_str(),
            "models": self.models,
            "custom_endpoints": self.custom_endpoints,
        }

    def __str__(self) -> str:
        """String represantation of the Project."""
        return "\n".join(f"{key}: {value}" for key, value in self.as_dict().items())


def get_project(server: str | None, token: str, organization_id: str, project_id: str) -> Project:
    """Return the project dict."""
    data = get(
        f"{server}/v1/organization/projects/{project_id}",
        token,
        item_name="Project",
        headers={"OpenAI-Organization": organization_id},
    )
    return Project(**data)


def list_projects(server: str | None, token: str, organization_id: str) -> list[Project]:
    """List projects."""
    data = get(
        f"{server}/v1/organization/projects",
        token,
        item_name="Project",
        headers={"OpenAI-Organization": organization_id},
    )
    return [Project(**org) for org in data["data"]]


def create_project(server: str | None, token: str, organization_id: str, data: dict[str, Any]) -> Project:
    """Create project."""
    project = post(
        f"{server}/v1/organization/projects",
        token,
        item_name="Project",
        headers={"OpenAI-Organization": organization_id},
        data=data,
    )
    return Project(**project)


def archive_project(server: str | None, token: str, organization_id: str, project_id: str) -> Project:
    """Create project."""
    data = post(
        f"{server}/v1/organization/projects/{project_id}/archive",
        token,
        item_name="Project",
        headers={"OpenAI-Organization": organization_id},
    )
    return Project(**data)
