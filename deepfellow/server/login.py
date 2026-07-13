# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
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
from deepfellow.common.state import state
from deepfellow.common.validation import validate_email, validate_password, validate_server
from deepfellow.server.utils.login import get_token_from_login, register_token

app = typer.Typer()


@app.command()
def login(
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Server address"),
    email: str | None = typer.Option(None, callback=validate_email, help="User email"),
    password: str | None = typer.Option(None, callback=validate_password, help="User password"),
    token: str | None = typer.Option(
        None, "--token", help="Register an already-obtained access token directly, skipping email/password login."
    ),
) -> None:
    """Login user and store the token in the secrets file.

    With `--token`, an already-obtained access token is validated against the server and stored
    directly instead of logging in with email/password — useful when the token came from
    elsewhere (e.g. a manual API call).

    Raises:
        typer.Exit if invalid credentials or the given token is rejected by the server.
    """
    secrets_file = state.cli_secrets_file
    server_url = get_server_url(server)
    if token is not None:
        register_token(secrets_file, server_url, token)
    else:
        get_token_from_login(secrets_file, server_url, email=email, password=password)
    echo.info("Your token is stored and will be used automatically.")
