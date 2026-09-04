# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server tool list command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.server.tool.utils import list_tools
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def list(
    project_id: str = typer.Argument(...),
    toolbox_id: str = typer.Argument(...),
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Server address"),
    organization_id: str | None = typer.Option(None, help="Organization ID, if your user belongs to more than one"),
    limit: int = typer.Option(100, min=1, max=200, help="Maximum number of tools to return"),
    after: str | None = typer.Option(None, help="Return tools created after this cursor ID"),
    before: str | None = typer.Option(None, help="Return tools created before this cursor ID"),
) -> None:
    """Display list of Tools in a Toolbox."""
    secrets_file = state.cli_secrets_file
    server_url = get_server_url(server)
    token = get_token(secrets_file, server_url)

    tools = list_tools(
        server_url, token, project_id, organization_id, toolbox_id, limit=limit, after=after, before=before
    )
    if not tools:
        echo.info("No tools found.")
        return

    echo.info("\n\n".join(str(tool) for tool in tools))
