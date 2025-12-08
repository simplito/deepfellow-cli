# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server organization delete command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.validation import validate_server
from deepfellow.server.organization.utils import delete_organization, get_organization
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def delete(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Server address"),
    organization_id: str = typer.Argument(...),
) -> None:
    """Delete organization after confirmation."""
    # Get token for the server
    secrets_file = ctx.obj.get("cli-secrets-file")
    server = get_server_url(server)
    token = get_token(secrets_file, server, None)

    organization = get_organization(server, organization_id, token)
    if not echo.confirm(f"Are you sure you want to delete the {organization.name}?", default=False):
        raise typer.Exit(1)

    delete_organization(server, organization_id, token)

    echo.info("Deleted {data['name']}")
