# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Model-listing core logic, shared across infra services."""

from typing import Any
from urllib.parse import quote

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import make_request
from deepfellow.infra.utils.connection import call_infra


def _is_valid_model_entry(item: Any) -> bool:
    """Return whether `item` has the fields callers of `get_service_models` rely on.

    Mirrors the backend's `RetrieveModelOut` schema, which requires `id`/`type` as strings and
    always reports `installed` (as `bool | InstallModelProgress | ModelInfo` - any value, so only
    its presence is checked, not its type).
    """
    return (
        isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("type"), str)
        and "installed" in item
    )


def get_service_models(
    server: str,
    api_key: str,
    service_id: str,
    quiet: bool = False,
    err_msg: str | None = None,
    installed: bool | None = None,
) -> list[dict[str, Any]]:
    """Fetch the raw list of a service's models (built-in and custom) via `GET .../services/{service_id}/models`.

    Args:
        server: Infra server URL.
        api_key: Infra admin API key.
        service_id: The service instance id to list models for (e.g. "ollama", "mcp").
        quiet: Forwarded to `call_infra` - see there.
        err_msg: Message shown on a transport/HTTP error. Defaults to a generic
            "Unable to list models for service '<service_id>'." when not given.
        installed: When given, forwarded as the backend's `installed` query filter, returning
            only installed (`True`) or only not-installed (`False`) models. `None` (default)
            fetches every model, regardless of install status.

    Returns:
        The raw list of model dicts from the response's `{"list": [...]}` envelope.
    """
    err_msg = err_msg or f"Unable to list models for service '{service_id}'."
    url = f"{server}/admin/services/{quote(service_id, safe='')}/models"
    if installed is not None:
        url += f"?installed={'true' if installed else 'false'}"
    data = call_infra(
        lambda: make_request(
            method="GET",
            url=url,
            token=api_key,
            err_msg=err_msg,
            reraise=True,
        ),
        err_msg,
        server=server,
        api_key=api_key,
        quiet=quiet,
    )
    items = data.get("list") if isinstance(data, dict) else None
    if not isinstance(items, list) or not all(_is_valid_model_entry(item) for item in items):
        echo.error(f"Unexpected response listing models for service '{service_id}'.")
        raise typer.Exit(1)
    return items
