# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server project api-key create command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.validation import validate_server
from deepfellow.server.project.api_key.utils import delete_api_key, get_api_key
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def revoke(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow server address"),
    organization_id: str = typer.Argument(..., help="Organization ID to add the API Key"),
    project_id: str = typer.Argument(..., help="Organization ID to add the API Key"),
    api_key_id: str = typer.Argument(..., help="Organization API Key to revoke"),
) -> None:
    """Revoke project API Key."""
    yes = ctx.obj.get("yes", False)
    if yes:
        echo.debug("Automatically confirming the revoke.")

    secrets_file = ctx.obj.get("cli-secrets-file")
    server = get_server_url(server)
    token = get_token(secrets_file, server)

    api_key = get_api_key(server, token, organization_id, project_id, api_key_id)

    if not yes and not echo.confirm(
        f"Are you sure you want to delete the Project API Key {api_key.name}?", default=False
    ):
        raise typer.Exit(1)

    delete_api_key(server, token, organization_id, project_id, api_key_id)

    echo.info("API Key revoked.")
