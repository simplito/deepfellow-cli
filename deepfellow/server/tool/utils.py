# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utils for the tool commands."""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import delete, get, make_request, post
from deepfellow.server.utils.headers import project_headers
from deepfellow.server.utils.time import datetime_to_str


@dataclass
class Tool:
    id: str
    definition: dict[str, Any]
    toolbox_id: str
    created_at: int

    def created_at_to_str(self) -> str:
        """Convert created_at to a localized date string."""
        return datetime_to_str(self.created_at)

    def as_dict(self) -> dict[str, Any]:
        """Dictionary representation of Tool."""
        return {
            "id": self.id,
            "toolbox_id": self.toolbox_id,
            "created_at": self.created_at_to_str(),
            "definition": json.dumps(self.definition, indent=2),
        }

    def __str__(self) -> str:
        """String represantation of the Tool."""
        return "\n".join(f"{key}: {value}" for key, value in self.as_dict().items())


def read_json_body(config: Path | None, what: str = "tool definition") -> dict[str, Any]:
    """Read a JSON object from a file, or from stdin if no file is given."""
    if config is None and sys.stdin.isatty():
        echo.error(f"No {what} provided. Pass --config <path> or pipe a JSON body on stdin.")
        raise typer.Exit(1)

    raw = config.read_text() if config is not None else sys.stdin.read()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        echo.error(f"Invalid {what} JSON: {exc}")
        raise typer.Exit(1) from exc

    if not isinstance(parsed, dict):
        echo.error(f"The {what} must be a JSON object.")
        raise typer.Exit(1)

    return parsed


def create_tool(
    server: str | None,
    token: str,
    project_id: str,
    organization_id: str | None,
    toolbox_id: str,
    definition: dict[str, Any],
) -> Tool:
    """Create a tool in a toolbox."""
    data = post(
        f"{server}/toolboxes/{toolbox_id}/tools",
        token,
        item_name="Tool",
        headers=project_headers(project_id, organization_id),
        data=definition,
    )
    return Tool(**data)


def list_tools(
    server: str | None,
    token: str,
    project_id: str,
    organization_id: str | None,
    toolbox_id: str,
    limit: int = 100,
    after: str | None = None,
    before: str | None = None,
) -> list[Tool]:
    """List tools in a toolbox."""
    params = {"limit": str(limit)}
    if after is not None:
        params["after"] = after
    if before is not None:
        params["before"] = before
    query = urlencode(params)
    data = get(
        f"{server}/toolboxes/{toolbox_id}/tools?{query}",
        token,
        item_name="Tools",
        headers=project_headers(project_id, organization_id),
    )
    return [Tool(**item) for item in data["data"]]


def get_tool(
    server: str | None, token: str, project_id: str, organization_id: str | None, toolbox_id: str, tool_id: str
) -> Tool:
    """Get a tool."""
    data = get(
        f"{server}/toolboxes/{toolbox_id}/tools/{tool_id}",
        token,
        item_name="Tool",
        headers=project_headers(project_id, organization_id),
    )
    return Tool(**data)


def update_tool(
    server: str | None,
    token: str,
    project_id: str,
    organization_id: str | None,
    toolbox_id: str,
    tool_id: str,
    update: dict[str, Any],
) -> Tool:
    """Update a tool with a partial definition update."""
    data = make_request(
        "POST",
        f"{server}/toolboxes/{toolbox_id}/tools/{tool_id}",
        token,
        headers=project_headers(project_id, organization_id),
        data=update,
        err_msg="Unable to update tool.",
    )
    return Tool(**data)


def delete_tool(
    server: str | None, token: str, project_id: str, organization_id: str | None, toolbox_id: str, tool_id: str
) -> None:
    """Delete a tool."""
    delete(
        f"{server}/toolboxes/{toolbox_id}/tools/{tool_id}",
        token,
        item_name="Tool",
        headers=project_headers(project_id, organization_id),
    )
