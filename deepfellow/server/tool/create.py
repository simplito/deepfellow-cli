# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server tool create command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.server.tool.utils import create_tool, read_json_body
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def create(
    project_id: str = typer.Argument(...),
    toolbox_id: str = typer.Argument(...),
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Server address"),
    organization_id: str | None = typer.Option(None, help="Organization ID, if your user belongs to more than one"),
    config: Path | None = typer.Option(
        None,
        "--config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to a JSON file with the tool definition (must include 'type'). Reads from stdin if omitted. "
        "Note: with --debug, the definition (which may include credentials, e.g. for an mcp/custom-mcp server) "
        "is printed to the console.",
    ),
) -> None:
    """Create a Tool in a Toolbox from a JSON tool definition.

    The definition is one of: file_search, mcp, image_generation, infra-mcp, custom-mcp, websearch.
    See the DeepFellow Server API docs for the fields each type requires.
    """
    definition = read_json_body(config)

    secrets_file = state.cli_secrets_file
    server_url = get_server_url(server)
    token = get_token(secrets_file, server_url)

    tool = create_tool(server_url, token, project_id, organization_id, toolbox_id, definition)

    echo.info(str(tool))
