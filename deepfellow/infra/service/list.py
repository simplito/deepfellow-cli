# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra service list command."""

from typing import Any, cast

import httpx
import typer

from deepfellow.common.config import read_env_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.rest import make_request
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server

app = typer.Typer()


def _is_installed(service: dict[str, Any]) -> bool:
    """Return whether a service is installed.

    The API reports ``installed`` as ``False`` when the service is not installed,
    and as a (possibly empty) dict of runtime config when it is.
    """
    return service.get("installed", False) is not False


def _format_service(service: dict[str, Any]) -> str:
    """Format a single installed service as readable ``key: value`` lines."""
    fields = {
        "id": service.get("id"),
        "type": service.get("type"),
        "instance": service.get("instance"),
        "description": service.get("description"),
        "downloaded": service.get("downloaded"),
    }
    return "\n".join(f"{key}: {value}" for key, value in fields.items())


@app.command()
def list(
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Infra address"),
) -> None:
    """Display list of installed services."""
    config_file = state.cli_config_file
    config = state.cli_config
    config_external_server = config.get("df_infra_external_url")
    secrets_file = state.cli_secrets_file

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

    url = f"{server}/admin/services"
    try:
        data = make_request(
            method="GET",
            url=url,
            token=api_key,
            err_msg="Unable to list services.",
            reraise=True,
        )
    except httpx.ConnectError as exc:
        echo.error("No connection with DeepFellow Infra. Is it up? (deepfellow infra start)")
        raise typer.Exit(1) from exc
    except httpx.HTTPStatusError as exc:
        msg = "Unable to list services"
        if exc.response:
            msg = exc.response.text

        echo.error(msg)
        raise typer.Exit(1) from exc

    services = [service for service in data.get("list", []) if _is_installed(service)]

    if not services:
        echo.info("No services installed.")
        return

    echo.info("\n\n".join(_format_service(service) for service in services))
