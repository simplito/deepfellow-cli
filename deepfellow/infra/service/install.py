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
from deepfellow.common.echo import echo, is_interactive
from deepfellow.common.env import env_set
from deepfellow.common.rest import post
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server, validate_url
from deepfellow.infra.utils.options import CLOUD_SERVICE_SPECS

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


def _build_spec(name: str, service_api_key: str | None) -> dict[str, str]:  # noqa: C901
    """Build spec dict for the given service name.

    For known cloud services, required fields with defaults are included automatically.
    Required fields without defaults are prompted interactively.
    Optional fields are omitted (the server applies its own defaults).
    """
    if name not in CLOUD_SERVICE_SPECS:
        return {}

    spec: dict[str, str] = {}
    for field_def in CLOUD_SERVICE_SPECS[name]:
        if field_def.name == "api_key":
            if service_api_key is not None:
                spec[field_def.name] = service_api_key
                continue
            if not field_def.required and not is_interactive():
                continue
            value = echo.prompt(
                f"{field_def.description}",
                password=True,
                default=field_def.default,
            )
            if not field_def.required and value == "" and is_interactive():
                confirmed = echo.confirm("Api Key is empty. Do you want to continue?")
                if not confirmed:
                    raise typer.Exit(1)
            if value != "":
                spec[field_def.name] = value
        elif field_def.required and field_def.default is not None:
            spec[field_def.name] = field_def.default
        elif field_def.required:
            value = echo.prompt(field_def.description)
            spec[field_def.name] = value
    return spec


@app.command()
def install(
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Infra address"),
    name: str = typer.Argument(..., help="service name (e.g. ollama)"),
    service_api_key: str | None = typer.Option(None, "--api-key", help="API key for remote services (e.g. claude)"),
    spec: str | None = typer.Option(
        None, help='Service configuration as a JSON object (e.g. \'{"url": "http://host:11434"}\')'
    ),
) -> None:
    """Install service."""
    parsed_spec: dict[str, Any] | None = _parse_spec(spec) if spec is not None else None

    config_file = state.cli_config_file
    config = state.cli_config
    config_external_server = config.get("df_infra_external_url")
    secrets_file = state.cli_secrets_file

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

    spec_res = parsed_spec if parsed_spec is not None else _build_spec(name, service_api_key)

    try:
        data = post(url, api_key, item_name="Service", data={"spec": spec_res}, reraise=True)
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
