# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install model core logic."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import InfraInstallSkippedError
from deepfellow.infra.utils.connection import call_infra, resolve_infra_connection
from deepfellow.infra.utils.progress import install_with_progress


def install(
    service_name: str,
    model_name: str,
    server: str | None = None,
) -> None:
    """Install model."""
    server, api_key = resolve_infra_connection(server)

    url = f"{server}/admin/services/{service_name}/models/_?model_id={model_name}"

    try:
        data = call_infra(
            lambda: install_with_progress(url, api_key, data={"spec": {}}),
            "Unable to install model.",
            server=server,
            api_key=api_key,
            skip_if_message_contains="already installed",
        )
    except InfraInstallSkippedError:
        echo.info(f"Model '{model_name}' is already installed; skipping.")
        return

    if data.get("status", "").lower() != "ok":
        message = data.get("details")
        echo.error(f"Unable to install model.{f' {message}' if message else ''}")
        if not message:
            echo.error("Check `docker compose logs infra` for details.")
        raise typer.Exit(1)

    echo.success(f"Model {model_name} installed.")
