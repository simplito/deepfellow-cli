# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Login command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.validation import validate_email, validate_password, validate_server
from deepfellow.server.utils.login import get_token_from_login

app = typer.Typer()


@app.command()
def login(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Server address"),
    email: str | None = typer.Option(None, callback=validate_email, help="User email"),
    password: str | None = typer.Option(None, callback=validate_password, help="User password"),
) -> None:
    """Login user and store the token in the secrets file.

    Raises:
        typer.Exit if invalid credentials.
    """
    secrets_file = ctx.obj.get("cli-secrets-file")
    server = get_server_url(server)
    get_token_from_login(secrets_file, server, email=email, password=password)
    echo.info("Your token is stored and will be used automatically.")
