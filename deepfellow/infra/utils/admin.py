# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared infra URL / admin API key resolution for admin-authenticated commands."""

from typing import Any, cast

import httpx
import typer

from deepfellow.common.config import read_env_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server


def resolve_infra_admin(server: str | None, api_key: str | None = None) -> tuple[str, str]:
    """Resolve the infra URL and admin API key, prompting if needed. Nothing is persisted here.

    Mirrors the resolution used by `infra service list`/`install` — the admin API key is read
    from the local secrets file, never from the remote instance.

    If `api_key` is given (e.g. via a command's `--api-key` option), it is used as-is instead of
    the stored/prompted value. The resolved values are only written back to the local config and
    secrets files by `infra_admin_request`, once a request actually confirms they work against
    the target — resolving them here does not touch disk, so a bad `--url`/`--api-key` (e.g.
    an unreachable address, a rejected key) never clobbers a previously working local config.
    """
    secrets_file = state.cli_secrets_file

    config_external_server = state.cli_config.get("df_infra_external_url")
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

    if api_key is not None:
        return server, api_key

    secrets = read_env_file(secrets_file) if secrets_file.is_file() else {}
    stored_key = secrets.get("DF_INFRA_ADMIN_API_KEY")
    if stored_key is None:
        stored_key = echo.prompt("Provide Infra Admin API Key", password=True)

    return server, stored_key


def persist_infra_admin(server: str, api_key: str, quiet: bool = False) -> None:
    """Persist a confirmed-working infra URL / admin API key pair to the local config and secrets files.

    Called only once a request against `server` using `api_key` has actually succeeded.
    `quiet` suppresses the "Updated ..." confirmation — used when a caller makes several requests
    against the same, already-confirmed server/key in a row (e.g. revealing multiple secrets), so
    the write isn't re-announced on every single one of them.
    """
    env_set(state.cli_config_file, "DF_INFRA_EXTERNAL_URL", server, should_raise=False, quiet=quiet)
    env_set(state.cli_secrets_file, "DF_INFRA_ADMIN_API_KEY", api_key, should_raise=False, quiet=quiet)


def infra_admin_request(
    method: str, url: str, server: str, api_key: str, json_body: dict[str, Any] | None = None, quiet: bool = False
) -> dict[str, Any]:
    """Perform an authenticated infra admin request.

    If the given key is rejected as invalid (401), prompts for a replacement and retries once —
    this is what makes `--api-key` optional day-to-day: a stored key is tried first, and you're
    only asked for a new one when it stops working. Only 401 triggers a reprompt; any other
    error status (403, 404, 5xx, ...) is terminal and reported via the generic error path below.

    `server` and the key that ends up working are persisted locally via `persist_infra_admin`
    only once the request actually succeeds — never eagerly, so a failed connection or a
    rejected key never clobbers a previously working local config. `quiet` is forwarded to
    `persist_infra_admin` — see there.
    """

    def _do(key: str) -> httpx.Response:
        try:
            return httpx.request(method, url, headers={"Authorization": f"Bearer {key}"}, json=json_body, timeout=30.0)
        except httpx.ConnectError as exc:
            echo.error("No connection with DeepFellow Infra. Is it up? (deepfellow infra start)")
            raise typer.Exit(1) from exc
        except httpx.HTTPError as exc:
            echo.error(f"HTTP request to {url} failed: {exc}")
            raise typer.Exit(1) from exc

    response = _do(api_key)

    if response.status_code == 401:
        echo.error("The Infra Admin API Key was rejected by the server.")
        api_key = echo.prompt("Provide a new Infra Admin API Key", password=True)
        response = _do(api_key)
        if response.status_code == 401:
            echo.error("The new Infra Admin API Key was also rejected by the server.")
            raise typer.Exit(1)

    if response.status_code >= 400:
        try:
            body = response.json()
        except ValueError:
            body = None
        detail = body.get("detail", response.text) if isinstance(body, dict) else response.text
        echo.error(f"Request failed ({response.status_code}): {detail}")
        raise typer.Exit(1)

    persist_infra_admin(server, api_key, quiet=quiet)
    try:
        return response.json()
    except ValueError as exc:
        echo.error(f"Unexpected response from {url}: not valid JSON.")
        echo.debug(exc)
        raise typer.Exit(1) from exc
