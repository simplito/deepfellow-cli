# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server opentelemetry command."""

import typer

from deepfellow.common.defaults import DEFAULT_OTEL_URL
from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url, make_request
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server, validate_url
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def opentelemetry(
    otel_url: str | None = typer.Argument(
        None,
        envvar="DF_OTEL_EXPORTER_OTLP_ENDPOINT",
        help="Open Telemetry url (DF_OTEL_EXPORTER_OTLP_ENDPOINT).",
        callback=validate_url,
    ),
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Server address"),
) -> None:
    """Connect the DeepFellow Server to Open Telemetry via PUT /admin/config. Applied without a restart."""
    secrets_file = state.cli_secrets_file
    server_url = get_server_url(server)
    token = get_token(secrets_file, server_url)

    if not otel_url:
        otel_url = echo.prompt_until_valid(
            "Provide OTL url",
            default=DEFAULT_OTEL_URL,
            validation=validate_url,
        )

    if otel_url:
        body = {"otel_exporter_otlp_endpoint": otel_url, "otel_tracing_enabled": True}
        make_request("PUT", f"{server_url}/admin/config", token, data=body, err_msg="Unable to update server config.")
        echo.success(f"DeepFellow Server is connected to Open Telemetry {otel_url}")
    else:
        echo.info("OpenTelemetry settings in DeepFellow remain the same as before")
