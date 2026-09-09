# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra mcp list command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.mcp import list_servers

app = typer.Typer()


@app.command()
def list(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
) -> None:
    """Display list of MCP servers."""
    servers = list_servers(server=server)
    if not servers:
        echo.info("No MCP servers provisioned.")
        return

    echo.info("\n\n".join(str(mcp_server) for mcp_server in servers))
