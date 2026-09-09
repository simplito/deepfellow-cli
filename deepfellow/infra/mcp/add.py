# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra mcp add command."""

import json
import sys
from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.mcp import add as add_util
from deepfellow.infra.utils.mcp import ensure_name_available

app = typer.Typer()

# Shown before prompting for a config path, and in --config's --help text, so the user knows
# what a "standard MCP client config" actually looks like without having to check the docs.
_CONFIG_EXAMPLE_HINT = (
    "An MCP client config is a JSON object mapping a server name to its launch parameters. Examples:\n"
    '  Local (stdio):  {"mcpServers": {"my-server": {"command": "npx", "args": ["-y", "some-mcp-server"]}}}\n'
    '  Remote (HTTP):  {"mcpServers": {"my-server": {"url": "https://example.com/mcp"}}}\n'
    'The "mcpServers" wrapper is optional - a bare {"command": ...}/{"url": ...} object also works.'
)


def _validate_config_path(value: str) -> Path:
    """Validate a user-entered path to an MCP config file."""
    path = Path(value).expanduser()
    if not path.is_file():
        raise typer.BadParameter(f"File not found: {path}")
    return path


@app.command()
def add(
    name: str = typer.Argument(..., help="Name to register the MCP server under."),
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
    config: Path | None = typer.Option(
        None,
        "--config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to a standard MCP client config JSON file. Reads from stdin if omitted. "
        "See the command's --help for an example.",
    ),
    prefix: str | None = typer.Option(
        None,
        "--prefix",
        help="Endpoint prefix for a Docker-image-based MCP server. Prompted for if omitted (only used "
        "when the config converts to a custom Docker image model).",
    ),
    image_port: int | None = typer.Option(
        None,
        "--image-port",
        help="Docker image port for a Docker-image-based MCP server. Prompted for if omitted (only used "
        "when the config converts to a custom Docker image model).",
    ),
) -> None:
    """Register an MCP server from a standard MCP client config JSON.

    A standard MCP client config is a JSON object mapping a server name to its launch
    parameters, e.g. {"mcpServers": {"my-server": {"command": "npx", "args": [...]}}} for a
    local (stdio) server, or {"mcpServers": {"my-server": {"url": "https://..."}}} for a remote
    (HTTP) one. The "mcpServers" wrapper is optional - a bare {"command": ...}/{"url": ...}
    object also works.

    This only registers the server's configuration - run `infra mcp install <name>` afterwards
    to actually start it.
    """
    server = ensure_name_available(name, server)

    if config is None and sys.stdin.isatty():
        # Nothing was piped and stdin is a real terminal, so reading it would just hang.
        # Ask for a path instead of erroring outright - but the user has no way to know what a
        # "standard MCP client config" is supposed to contain, so show an example first.
        echo.info(_CONFIG_EXAMPLE_HINT)
        config = echo.prompt_until_valid(
            "Path to a standard MCP client config JSON file",
            _validate_config_path,
            error_message="File not found or not readable.",
        )

    if config is not None:
        try:
            raw = config.read_text()
        except (OSError, UnicodeDecodeError) as exc:
            echo.error(f"Unable to read MCP config file: {exc}")
            reraise_if_debug(exc)
    else:
        raw = sys.stdin.read()

    if not raw.strip():
        echo.error("No MCP config provided. Pass --config <path> or pipe a config JSON on stdin.")
        raise typer.Exit(1)

    try:
        parsed_config = json.loads(raw)
    except json.JSONDecodeError as exc:
        echo.error(f"Invalid MCP config JSON: {exc}")
        reraise_if_debug(exc)
    if not isinstance(parsed_config, dict):
        echo.error("MCP config must be a JSON object.")
        raise typer.Exit(1)

    custom_model_id = add_util(
        name=name,
        config=parsed_config,
        server=server,
        prefix=prefix,
        image_port=image_port,
        stdin_is_tty=sys.stdin.isatty(),
    )

    if state.debug:
        echo.debug(f"custom_model_id: {custom_model_id}")
    echo.success(f"MCP server '{name}' registered. Run `infra mcp install {name}` to start it.")
