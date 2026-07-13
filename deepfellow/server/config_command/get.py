# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server config get command."""

import json

import typer

from deepfellow.common.config import reveal_masked_paths
from deepfellow.common.echo import echo
from deepfellow.common.rest import get as http_get
from deepfellow.common.rest import get_server_url
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command(name="get")
def get_(
    server: str | None = typer.Option(None, "--server", callback=validate_server, help="DeepFellow Server address"),
    secret: bool = typer.Option(False, "--secret", help="Reveal secret field values instead of masking them."),
) -> None:
    """Read dynamic server configuration via GET /admin/config. Secret fields are masked unless --secret is given."""
    secrets_file = state.cli_secrets_file
    server_url = get_server_url(server)
    token = get_token(secrets_file, server_url)

    config = http_get(f"{server_url}/admin/config", token, item_name="Server config")

    if secret:
        reveal_masked_paths(
            config,
            lambda path: http_get(
                f"{server_url}/admin/config/reveal/{path}", token, item_name=f"secret value for {path}"
            )["value"],
        )

    echo.info(json.dumps(config, indent=2, ensure_ascii=False))
