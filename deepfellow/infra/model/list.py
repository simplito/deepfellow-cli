# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra model list command."""

from typing import Any

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.connection import is_installed, resolve_infra_connection
from deepfellow.infra.utils.models import get_service_models

app = typer.Typer()


def _format_model(model: dict[str, Any]) -> str:
    """Format a single model entry as readable ``key: value`` lines."""
    fields = {
        "id": model.get("id"),
        "type": model.get("type"),
        "size": model.get("size"),
        "installed": is_installed(model.get("installed", False)),
    }
    lines = [f"{key}: {value}" for key, value in fields.items()]

    description = model.get("description")
    if isinstance(description, str) and description:
        lines.append(f"description: {description}")

    return "\n".join(lines)


@app.command()
def list(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
    service_name: str = typer.Argument(..., help="service name (e.g. ollama)"),
    installed: bool | None = typer.Option(
        None,
        "--installed/--no-installed",
        help="Only show installed (--installed) or not-installed (--no-installed) models. Shows all by default.",
    ),
) -> None:
    """Display list of models available on a service."""
    server, api_key = resolve_infra_connection(server)

    # quiet=True: a read-only list shouldn't re-announce "Updated config/secrets" every time it's
    # run against an already-known, already-working connection.
    models = get_service_models(server, api_key, service_name, quiet=True, installed=installed)

    if not models:
        echo.info("No models available.")
        return

    echo.info("\n\n".join(_format_model(model) for model in models))
