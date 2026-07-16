# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server config set command."""

import json

import typer

from deepfellow.common.config import parse_key_value_updates, reveal_masked_paths
from deepfellow.common.echo import echo
from deepfellow.common.rest import get as http_get
from deepfellow.common.rest import get_server_url, make_request
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command(name="set")
def set_(
    updates: list[str] = typer.Argument(..., help="Fields to update, e.g. otel_tracing_enabled=true"),
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Server address"),
    secret: bool = typer.Option(False, "--secret", help="Reveal secret field values instead of masking them."),
) -> None:
    """Update dynamic server configuration via PUT /admin/config. Applied without a restart."""
    secrets_file = state.cli_secrets_file
    server_url = get_server_url(server)
    token = get_token(secrets_file, server_url)

    body = parse_key_value_updates(updates)
    url = f"{server_url}/admin/config"
    result = make_request("PUT", url, token, data=body, err_msg="Unable to update server config.")
    echo.success("Server config updated.")

    if secret:
        reveal_masked_paths(
            result,
            lambda path: http_get(
                f"{server_url}/admin/config/reveal/{path}", token, item_name=f"secret value for {path}"
            )["value"],
        )

    echo.info(json.dumps(result, indent=2, ensure_ascii=False))
