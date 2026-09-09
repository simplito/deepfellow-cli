# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra mcp install command."""

from typing import Annotated

import typer

from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.mcp import install as install_util

app = typer.Typer()


@app.command()
def install(
    name: str = typer.Argument(
        ..., help="Name of the MCP server to install (e.g. brave-search, or one added via `add`)."
    ),
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
    api_key: str | None = typer.Option(None, "--api-key", help="API key for MCP servers with an api_key field"),
    spec: str | None = typer.Option(
        None, help='MCP server configuration as a JSON object (e.g. \'{"envs": {"BRAVE_API_KEY": "..."}}\')'
    ),
    set_args: Annotated[
        list[str] | None, typer.Option("--set", help='Set a field (e.g. --set envs=\'{"BRAVE_API_KEY": "..."}\')')
    ] = None,
    prompt_all: Annotated[bool, typer.Option(help="Prompt for all fields including optional ones")] = True,
) -> None:
    """Install (start) an MCP server, prompting for any required fields it needs.

    Run `infra mcp list` first to see which built-in servers are available and which are already
    installed. A server added via `infra mcp add` also needs this command afterwards to actually
    start it - `add` only registers its configuration.
    """
    install_util(name=name, server=server, api_key=api_key, spec=spec, set_args=set_args, prompt_all=prompt_all)
