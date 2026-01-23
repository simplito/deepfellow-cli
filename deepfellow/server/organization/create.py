# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server organization create command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.validation import validate_server
from deepfellow.server.organization.utils import create_organization
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def create(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Server address"),
    name: str = typer.Argument(...),
) -> None:
    """Create organization."""
    # Get token for the server
    secrets_file = ctx.obj.get("cli-secrets-file")
    server_url = get_server_url(server)
    token = get_token(secrets_file, server_url)

    organization = create_organization(server_url, token, name)

    echo.info(str(organization))
