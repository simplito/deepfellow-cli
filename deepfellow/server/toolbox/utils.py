# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utils for the toolbox commands."""

from dataclasses import dataclass
from urllib.parse import urlencode

from deepfellow.common.rest import delete, get, make_request, post
from deepfellow.server.utils.headers import project_headers
from deepfellow.server.utils.time import datetime_to_str


@dataclass
class Toolbox:
    id: str
    name: str
    project_id: str
    created_at: int

    def created_at_to_str(self) -> str:
        """Convert created_at to a localized date string."""
        return datetime_to_str(self.created_at)

    def as_dict(self) -> dict[str, str]:
        """Dictionary representation of Toolbox."""
        return {
            "id": self.id,
            "name": self.name,
            "project_id": self.project_id,
            "created_at": self.created_at_to_str(),
        }

    def __str__(self) -> str:
        """String represantation of the Toolbox."""
        return "\n".join(f"{key}: {value}" for key, value in self.as_dict().items())


def create_toolbox(server: str | None, token: str, project_id: str, organization_id: str | None, name: str) -> Toolbox:
    """Create a toolbox."""
    data = post(
        f"{server}/toolboxes",
        token,
        item_name="Toolbox",
        headers=project_headers(project_id, organization_id),
        data={"name": name},
    )
    return Toolbox(**data)


def list_toolboxes(
    server: str | None,
    token: str,
    project_id: str,
    organization_id: str | None,
    limit: int = 100,
    after: str | None = None,
    before: str | None = None,
) -> list[Toolbox]:
    """List toolboxes."""
    params = {"limit": str(limit)}
    if after is not None:
        params["after"] = after
    if before is not None:
        params["before"] = before
    query = urlencode(params)
    data = get(
        f"{server}/toolboxes?{query}",
        token,
        item_name="Toolboxes",
        headers=project_headers(project_id, organization_id),
    )
    return [Toolbox(**item) for item in data["data"]]


def get_toolbox(
    server: str | None, token: str, project_id: str, organization_id: str | None, toolbox_id: str
) -> Toolbox:
    """Get a toolbox."""
    data = get(
        f"{server}/toolboxes/{toolbox_id}",
        token,
        item_name="Toolbox",
        headers=project_headers(project_id, organization_id),
    )
    return Toolbox(**data)


def update_toolbox(
    server: str | None, token: str, project_id: str, organization_id: str | None, toolbox_id: str, name: str
) -> Toolbox:
    """Update a toolbox."""
    data = make_request(
        "POST",
        f"{server}/toolboxes/{toolbox_id}",
        token,
        headers=project_headers(project_id, organization_id),
        data={"name": name},
        err_msg="Unable to update toolbox.",
    )
    return Toolbox(**data)


def delete_toolbox(
    server: str | None, token: str, project_id: str, organization_id: str | None, toolbox_id: str
) -> None:
    """Delete a toolbox."""
    delete(
        f"{server}/toolboxes/{toolbox_id}",
        token,
        item_name="Toolbox",
        headers=project_headers(project_id, organization_id),
    )
