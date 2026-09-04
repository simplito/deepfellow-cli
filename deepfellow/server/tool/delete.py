# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server tool delete command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.server.tool.utils import delete_tool, get_tool
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def delete(
    project_id: str = typer.Argument(...),
    toolbox_id: str = typer.Argument(...),
    tool_id: str = typer.Argument(...),
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Server address"),
    organization_id: str | None = typer.Option(None, help="Organization ID, if your user belongs to more than one"),
) -> None:
    """Delete a Tool."""
    yes = state.yes
    if yes:
        echo.debug("Automatically confirming the delete.")

    secrets_file = state.cli_secrets_file
    server_url = get_server_url(server)
    token = get_token(secrets_file, server_url)

    get_tool(server_url, token, project_id, organization_id, toolbox_id, tool_id)

    if not yes and not echo.confirm(
        f"Are you sure you want to delete the tool '{tool_id}'? This action cannot be undone.", default=False
    ):
        raise typer.Exit(1)

    delete_tool(server_url, token, project_id, organization_id, toolbox_id, tool_id)

    echo.success(f"Tool '{tool_id}' deleted.")
