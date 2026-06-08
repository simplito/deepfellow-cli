# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra service install command."""

import json
from typing import Any, cast

import httpx
import typer

from deepfellow.common.config import read_env_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.rest import post
from deepfellow.common.validation import validate_server, validate_url

app = typer.Typer()


def _parse_spec(spec: str | None) -> dict[str, Any]:
    if spec is None:
        return {}
    try:
        parsed = json.loads(spec)
    except json.JSONDecodeError as exc:
        echo.error(f"Invalid JSON in --spec: {exc}")
        raise typer.Exit(1) from exc
    if not isinstance(parsed, dict):
        echo.error("--spec must be a JSON object, not an array or scalar.")
        raise typer.Exit(1)
    return parsed


@app.command()
def install(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Infra address"),
    name: str = typer.Argument(..., help="service name (e.g. ollama)"),
    spec: str | None = typer.Option(
        None, help='Service configuration as a JSON object (e.g. \'{"url": "http://host:11434"}\')'
    ),
) -> None:
    """Install service."""
    parsed_spec = _parse_spec(spec)

    config_file = ctx.obj.get("cli-config-file")
    config = ctx.obj.get("cli-config")
    config_external_server = config.get("df_infra_external_url")
    secrets_file = ctx.obj.get("cli-secrets-file")

    if server is None:
        if config_external_server is not None:
            server = config_external_server
        else:
            server = echo.prompt_until_valid(
                "Provide a DF_INFRA_URL for this Infra. e.g. http://infra:8086",
                validate_url,
                error_message="Invalid DF_INFRA_URL. Please try again.",
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
        data = post(url, api_key, item_name="Service", data={"spec": parsed_spec}, reraise=True)
    except httpx.ConnectError as exc:
        echo.error("No connection with DeepFellow Infra. Is it up? (deepfellow infra start)")
        raise typer.Exit(1) from exc
    except httpx.HTTPStatusError as exc:
        msg = "Unable to install service"
        if exc.response:
            msg = exc.response.text

        echo.error(msg)
        raise typer.Exit(1) from exc

    if data.get("status") != "OK":
        echo.error("Unable to install service.")
        raise typer.Exit(1)

    echo.success(f"Service {name} installed.")
