# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server project update command."""

from typing import Any, Literal

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.server.project.utils import get_project, update_project
from deepfellow.server.utils.login import get_token

app = typer.Typer()


def _merge_or_replace(
    new_items: list[str], current_value: list[str] | Literal["all"], replace: bool, flag: str
) -> list[str]:
    """Return the resolved list value for a single list field.

    In replace mode, returns `new_items` as-is. Otherwise, adds `new_items` to `current_value`,
    skipping items already present. Raises if `current_value` is 'all', since there's nothing to add to.
    """
    if replace:
        return new_items

    if current_value == "all":
        raise typer.BadParameter(f"Project's {flag} is currently 'all' - use --overwrite to replace it")

    return list(dict.fromkeys(current_value + new_items))


@app.command()
def update(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Server address"),
    organization_id: str = typer.Argument(...),
    project_id: str = typer.Argument(...),
    name: str | None = typer.Option(None, help="Rename the Project to this value"),
    models: list[str] | None = typer.Option(
        None, help="Add these models to the Project's allowed models, or 'all' for every model"
    ),
    custom_endpoints: list[str] | None = typer.Option(
        None, help="Add these custom endpoints to the Project's custom endpoints, or 'all' for every endpoint"
    ),
    mcp_prefixes: list[str] | None = typer.Option(
        None, help="Add these MCP server prefixes to the Project's MCP server prefixes, or 'all' for every prefix"
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Replace --models/--custom-endpoints/--mcp-prefixes with exactly the given list, "
        "instead of adding to what's already there. Place this before those options.",
    ),
) -> None:
    """Update an existing Project."""
    secrets_file = state.cli_secrets_file
    server_url = get_server_url(server)
    token = get_token(secrets_file, server_url)

    if models and "all" in models and len(models) > 1:
        raise typer.BadParameter("Cannot mix 'all' with specific models")
    if custom_endpoints and "all" in custom_endpoints and len(custom_endpoints) > 1:
        raise typer.BadParameter("Cannot mix 'all' with specific custom endpoints")
    if mcp_prefixes and "all" in mcp_prefixes and len(mcp_prefixes) > 1:
        raise typer.BadParameter("Cannot mix 'all' with specific MCP prefixes")

    data: dict[str, Any] = {}
    if name is not None:
        data["name"] = name

    models_is_all_keyword = models == ["all"]
    custom_endpoints_is_all_keyword = custom_endpoints == ["all"]
    mcp_prefixes_is_all_keyword = mcp_prefixes == ["all"]
    needs_current = not overwrite and (
        (models is not None and not models_is_all_keyword)
        or (custom_endpoints is not None and not custom_endpoints_is_all_keyword)
        or (mcp_prefixes is not None and not mcp_prefixes_is_all_keyword)
    )
    current = get_project(server_url, token, organization_id, project_id) if needs_current else None

    if models is not None:
        data["models"] = (
            "all"
            if models_is_all_keyword
            else _merge_or_replace(models, current.models if current else [], overwrite, "--models")
        )
    if custom_endpoints is not None:
        data["custom_endpoints"] = (
            "all"
            if custom_endpoints_is_all_keyword
            else _merge_or_replace(
                custom_endpoints, current.custom_endpoints if current else [], overwrite, "--custom-endpoints"
            )
        )
    if mcp_prefixes is not None:
        data["mcp_prefixes"] = (
            "all"
            if mcp_prefixes_is_all_keyword
            else _merge_or_replace(mcp_prefixes, current.mcp_prefixes if current else [], overwrite, "--mcp-prefixes")
        )

    if not data:
        raise typer.BadParameter(
            "Provide at least one of --name, --models, --custom-endpoints, --mcp-prefixes to update"
        )

    project = update_project(server_url, token, organization_id, project_id, data)

    echo.info(str(project))
