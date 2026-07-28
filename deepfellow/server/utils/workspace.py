# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utils for the atomic workspace-creation request."""

from dataclasses import dataclass

from deepfellow.common.rest import post
from deepfellow.server.organization.utils import Organization
from deepfellow.server.project.api_key.utils import ApiKey
from deepfellow.server.project.utils import Project


@dataclass
class Workspace:
    organization: Organization
    project: Project
    api_key: ApiKey

    def __str__(self) -> str:
        """String representation of the Workspace."""
        return "\n".join(
            [
                "organization:",
                str(self.organization),
                "project:",
                str(self.project),
                "api_key:",
                str(self.api_key),
            ]
        )


def create_workspace(
    server: str | None, token: str, organization_name: str, project_name: str, api_key_name: str
) -> Workspace:
    """Create an organization, a project, and a project API key in one call.

    Calls the server's `POST /admin/workspace` endpoint, which performs the three creations atomically
    (with server-side compensating rollback if project or API-key creation fails partway through).
    """
    data = post(
        f"{server}/admin/workspace/",
        token,
        item_name="Workspace",
        data={
            "organization_name": organization_name,
            "project_name": project_name,
            "api_key_name": api_key_name,
        },
    )
    return Workspace(
        organization=Organization(**data["organization"]),
        project=Project(**data["project"]),
        api_key=ApiKey.from_data(data["api_key"]),
    )
