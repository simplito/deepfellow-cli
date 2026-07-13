# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra config get command."""

import json

import typer

from deepfellow.common.config import reveal_secret_entries
from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.admin import infra_admin_request, resolve_infra_admin

app = typer.Typer()


@app.command(name="get")
def get_(
    server: str | None = typer.Option(None, "--server", callback=validate_server, help="DeepFellow Infra address"),
    api_key: str | None = typer.Option(
        None, "--api-key", help="Infra Admin API Key to use, instead of the one currently stored locally."
    ),
    secret: bool = typer.Option(False, "--secret", help="Reveal secret field values instead of masking them."),
) -> None:
    """Read dynamic infra configuration via GET /admin/config. Secret fields are masked unless --secret is given."""
    server_url, resolved_key = resolve_infra_admin(server, api_key=api_key)

    config = infra_admin_request("GET", f"{server_url}/admin/config", server_url, resolved_key)

    if secret:
        reveal_secret_entries(
            config,
            lambda key: infra_admin_request(
                "GET", f"{server_url}/admin/config/{key}/reveal", server_url, resolved_key, quiet=True
            )["value"],
        )

    echo.info(json.dumps(config, indent=2, ensure_ascii=False))
