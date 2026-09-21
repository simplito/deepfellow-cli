# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra service list command."""

from typing import Any

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import make_request
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.connection import call_infra, is_installed, resolve_infra_connection

app = typer.Typer()


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
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
) -> None:
    """Display list of installed services."""
    server, api_key = resolve_infra_connection(server)

    url = f"{server}/admin/services"
    data = call_infra(
        lambda: make_request(
            method="GET",
            url=url,
            token=api_key,
            err_msg="Unable to list services.",
            reraise=True,
        ),
        "Unable to list services.",
        server=server,
        api_key=api_key,
    )

    services = [service for service in data.get("list", []) if is_installed(service.get("installed", False))]

    if not services:
        echo.info("No services installed.")
        return

    echo.info("\n\n".join(_format_service(service) for service in services))
