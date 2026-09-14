# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra service install command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import make_request
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.connection import call_infra, resolve_infra_connection

app = typer.Typer()


@app.command()
def uninstall(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
    name: str = typer.Argument(..., help="service name (e.g. ollama)"),
    purge: bool = typer.Option(False, help="Remove service with all its files."),
) -> None:
    """Uninstall service."""
    server, api_key = resolve_infra_connection(server)

    url = f"{server}/admin/services/{name}"

    data = call_infra(
        lambda: make_request(
            method="DELETE",
            url=url,
            token=api_key,
            data={"purge": purge},
            err_msg="Unable to uninstall Service.",
            reraise=True,
        ),
        "Unable to uninstall service.",
        server=server,
        api_key=api_key,
    )

    if data.get("status") != "OK":
        echo.error("Unable to uninstall service.")
        raise typer.Exit(1)

    echo.success(f"Service {name} uninstalled.")
