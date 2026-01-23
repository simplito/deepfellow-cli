# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra service install command."""

from typing import cast

import httpx
import typer

from deepfellow.common.config import read_env_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.rest import make_request
from deepfellow.common.validation import validate_server

app = typer.Typer()


@app.command()
def uninstall(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Infra address"),
    name: str = typer.Argument(..., help="service name (e.g. ollama)"),
) -> None:
    """Uninstall service."""
    # Get token for the server
    config_file = ctx.obj.get("cli-config-file")
    config = ctx.obj.get("cli-config")
    config_external_server = config.get("df_infra_external_url")
    secrets_file = ctx.obj.get("cli-secrets-file")

    if server is None:
        if config_external_server is not None:
            server = config_external_server
        else:
            server = echo.prompt_until_valid(
                message="Provide DeepFellow Infra URL",
                validation=validate_server,
                error_message="Invalid Deepfellow Infra address. Please try again.",
            )

    server = cast("str", server)
    if server != config_external_server:
        env_set(config_file, "DF_INFRA_EXTERNAL_URL", server, should_raise=False)

    secrets = read_env_file(secrets_file) if secrets_file.is_file() else {}
    api_key = secrets.get("DF_INFRA_ADMIN_API_KEY")
    if api_key is None:
        api_key = echo.prompt("Provide Infra Admin API Key", password=True)
        env_set(secrets_file, "DF_INFRA_ADMIN_API_KEY", api_key, should_raise=False)

    url = f"{server}/admin/services/{name}"

    try:
        data = make_request(
            method="DELETE",
            url=url,
            token=api_key,
            data={"purge": False},
            err_msg="Unable to uninstall Service.",
            reraise=True,
        )
    except httpx.ConnectError as exc:
        echo.error("No connection with DeepFellow Infra. Is it up? (deepfellow infra start)")
        raise typer.Exit(1) from exc
    except httpx.HTTPStatusError as exc:
        msg = "Unable to uninstall service"
        if exc.response:
            msg = exc.response.text

        echo.error(msg)
        raise typer.Exit(1) from exc

    if data.get("status") != "OK":
        echo.error("Unable to uninstall service.")
        raise typer.Exit(1)

    echo.success(f"Service {name} uninstalled.")
