# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server organization get command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.validation import validate_server
from deepfellow.server.organization.utils import get_organization
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def get(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Server address"),
    organization_id: str = typer.Argument(...),
) -> None:
    """Display organization info."""
    # Get token for the server
    secrets_file = ctx.obj.get("cli-secrets-file")
    server = get_server_url(server)
    token = get_token(secrets_file, server)

    organization = get_organization(server, organization_id, token)

    # Response

    echo.info(str(organization))
