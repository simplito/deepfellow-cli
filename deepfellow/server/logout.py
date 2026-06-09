# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Logout command."""

import httpx
import typer

from deepfellow.common.config import read_env_file, save_env_file
from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.state import state
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def logout() -> None:
    """Logout user and invalidate token on the server."""
    secrets_file = state.cli_secrets_file
    server_url = get_server_url(None)
    token = get_token(secrets_file, server_url)

    url = f"{server_url}/auth/logout"
    echo.debug(f"POST {url}")
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        echo.warning("Could not invalidate token on the server. Clearing locally.")
        echo.debug(exc)

    secrets = read_env_file(secrets_file) if secrets_file.is_file() else {}
    secrets.pop("DF_USER_TOKEN", None)
    secrets.pop("DF_USER_REFRESH_TOKEN", None)

    save_env_file(secrets_file, secrets, docker_note=False, quiet=True)
    echo.success("Logged out successfully.")
