# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Infra connection resolution utilities."""

import time
from collections.abc import Callable
from json import JSONDecodeError
from typing import Any, cast
from urllib.parse import quote

import httpx
import typer

from deepfellow.common.config import read_env_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.exceptions import InfraInstallSkippedError
from deepfellow.common.state import state
from deepfellow.common.validation import validate_url

# How long to keep retrying a "some other run left this installing" response before giving up,
# and how long to wait between attempts. The timeout mirrors install_with_progress's own read
# timeout for a single install/download - a resumed wait is given the same overall budget.
INSTALL_RETRY_TIMEOUT_SECONDS = 60 * 60 * 24
INSTALL_RETRY_INTERVAL_SECONDS = 10.0


def resolve_infra_connection(server: str | None) -> tuple[str, str]:
    """Resolve infra server URL and admin API key from config, secrets, or interactive prompts.

    Nothing is persisted here. The resolved values are only written back to the local config and
    secrets files by `persist_infra_connection`, once a request actually confirms they work against
    the target — resolving them here does not touch disk, so a bad `--url`/API key (e.g. an
    unreachable address, a rejected key) never clobbers a previously working local config.

    Args:
        server: Server URL passed via CLI option, or None to fall back to config/prompt.

    Returns:
        Tuple of (server_url, api_key).
    """
    config = state.cli_config
    config_external_server = config.get("df_infra_external_url")
    secrets_file = state.cli_secrets_file

    if server is None:
        if config_external_server is not None:
            server = config_external_server
        else:
            server = echo.prompt_until_valid(
                "Provide an external URL for this Infra. e.g. http://localhost:8086",
                validate_url,
                error_message="Invalid URL. Please try again.",
            )

    server = cast("str", server)

    secrets = read_env_file(secrets_file) if secrets_file.is_file() else {}
    api_key = secrets.get("DF_INFRA_ADMIN_API_KEY")
    if api_key is None:
        api_key = echo.prompt("Provide Infra Admin API Key", password=True)

    return server, cast("str", api_key)


def cancel_service_install(server: str, api_key: str, service_id: str) -> None:
    """Best-effort cancel of an in-progress service install/update on the Infra server.

    Meant to be called from a `KeyboardInterrupt` handler: never raises. A 404 (nothing was
    installing) is treated as success; any other failure is only warned about, so it can never
    replace the interrupt as the reason the command is exiting.

    Args:
        server: Infra server URL.
        api_key: Infra admin API key.
        service_id: The service instance id to cancel (e.g. "ollama").
    """
    url = f"{server}/admin/services/{quote(service_id, safe='')}/cancel"
    _cancel(url, api_key, f"service '{service_id}'")


def cancel_model_install(server: str, api_key: str, service_id: str, model_id: str) -> None:
    """Best-effort cancel of an in-progress model install on the Infra server. See `cancel_service_install`.

    Args:
        server: Infra server URL.
        api_key: Infra admin API key.
        service_id: The service instance id the model belongs to (e.g. "ollama").
        model_id: The model id to cancel (e.g. "llama-3.1-8B").
    """
    url = f"{server}/admin/services/{quote(service_id, safe='')}/models/cancel?model_id={quote(model_id, safe='')}"
    _cancel(url, api_key, f"model '{model_id}'")


def _cancel(url: str, api_key: str, description: str) -> None:
    """POST a cancel request, swallowing a 404 and warning (never raising) on any other failure.

    Args:
        url: Full cancel endpoint URL to POST to.
        api_key: Infra admin API key.
        description: Human-readable description of what's being cancelled, used in the warning
            message on failure (e.g. "service 'ollama'").
    """
    echo.debug(f"POST {url}")
    try:
        response = httpx.post(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=30.0)
        if response.status_code == 404:
            echo.debug(f"{description}: nothing was installing (404); nothing to cancel.")
            return
        response.raise_for_status()
    except httpx.HTTPError as exc:
        echo.warning(f"Could not cancel {description} install on Infra; it may still be running there. ({exc})")


def persist_infra_connection(server: str, api_key: str, quiet: bool = False) -> None:
    """Persist a confirmed-working infra URL / admin API key pair to the local config and secrets files.

    Called only once a request against `server` using `api_key` has actually succeeded.
    `quiet` suppresses the "Updated ..." confirmation — used when a caller makes several requests
    against the same, already-confirmed server/key in a row, so the write isn't re-announced every time.
    """
    env_set(state.cli_config_file, "DF_INFRA_EXTERNAL_URL", server, should_raise=False, quiet=quiet)
    env_set(state.cli_secrets_file, "DF_INFRA_ADMIN_API_KEY", api_key, should_raise=False, quiet=quiet)


def call_infra(
    request: Callable[[], dict[str, Any]],
    default_error_msg: str,
    server: str | None = None,
    api_key: str | None = None,
    quiet: bool = False,
    skip_if_message_contains: str | None = None,
    retry_if_message_contains: str | None = None,
) -> dict[str, Any]:
    """Call the Infra API, translating transport errors into user-facing messages.

    ``request`` must invoke the REST helper with ``reraise=True`` so ``httpx`` errors
    propagate here instead of being swallowed with a generic message.

    Args:
        request: Zero-argument callable performing the REST call (e.g. ``lambda: get(...)``). Called
            again, unmodified, on each retry - so it must perform a fresh request every time, not
            replay a cached one.
        default_error_msg: Message shown when an HTTP error response has no body.
        server: If given (together with `api_key`), persisted via `persist_infra_connection`
            once `request` succeeds — never before, so a bad `server`/`api_key` never clobbers
            a previously working local config.
        api_key: See `server`.
        quiet: Forwarded to `persist_infra_connection` — see there.
        skip_if_message_contains: When the error message extracted from an ``httpx.HTTPStatusError``
            response contains this substring, raise ``InfraInstallSkippedError`` instead of echoing an
            error and exiting — lets the caller treat it as a no-op.
        retry_if_message_contains: When the error message extracted from an ``httpx.HTTPStatusError``
            response contains this substring, wait `INSTALL_RETRY_INTERVAL_SECONDS` and call
            `request` again instead of failing — for a job some other, likely interrupted, run left
            running server-side (the CLI has no way to reattach to its progress, only to poll until
            it clears). Retries for up to `INSTALL_RETRY_TIMEOUT_SECONDS`, then fails normally.

    Returns:
        The parsed JSON response.

    Raises:
        InfraInstallSkippedError: if the extracted error message matches `skip_if_message_contains`.
    """
    deadline = time.monotonic() + INSTALL_RETRY_TIMEOUT_SECONDS
    start = time.monotonic()
    announced = False

    while True:
        try:
            result = request()
        except httpx.ConnectError as exc:
            echo.error("No connection with DeepFellow Infra. Is it up? (deepfellow infra start)")
            raise typer.Exit(1) from exc
        except httpx.HTTPStatusError as exc:
            message = _error_message(exc.response, default_error_msg)
            if skip_if_message_contains and skip_if_message_contains in message:
                raise InfraInstallSkippedError(message) from exc
            if retry_if_message_contains and retry_if_message_contains in message and time.monotonic() < deadline:
                if not announced:
                    echo.info(f"{message}; waiting for it to finish before retrying...")
                    announced = True
                else:
                    echo.info(f"Still waiting... ({int(time.monotonic() - start)}s)")
                time.sleep(INSTALL_RETRY_INTERVAL_SECONDS)
                continue
            echo.error(message)
            raise typer.Exit(1) from exc
        except httpx.HTTPError as exc:
            echo.error(default_error_msg)
            raise typer.Exit(1) from exc
        break

    if server is not None and api_key is not None:
        persist_infra_connection(server, api_key, quiet=quiet)

    return result


def is_installed(value: Any) -> bool:
    """Return whether an ``installed`` field value, as reported by an infra service/model entry, means installed.

    The API reports an entry as not installed via a literal `False`; any other value - `True`, an
    empty or populated dict of runtime config, or an install-progress dict - means installed.

    Args:
        value: The raw `installed` field value from a service/model entry (e.g. `entry.get("installed", False)`).

    Returns:
        Whether the entry is installed.
    """
    return value is not False


def cancel_on_interrupt(
    call: Callable[[], dict[str, Any]], cancel: Callable[[], None], description: str
) -> dict[str, Any]:
    """Run `call`, best-effort cancelling the matching install on Infra if interrupted, then re-raising.

    Meant to wrap a `call_infra(...)` call for a long-running install, covering both its SSE
    progress read and its own "already installing" retry-wait - a `KeyboardInterrupt` landing in
    either would otherwise just abandon the install running server-side. Any other exception
    `call` raises (e.g. `InfraInstallSkippedError`) passes through untouched. `cancel` itself is
    never allowed to replace the original `KeyboardInterrupt`: whatever it raises is caught and
    warned about here, so the interrupt is always what actually propagates.

    Args:
        call: Zero-argument callable performing the install (e.g. `lambda: call_infra(...)`).
        cancel: Zero-argument callable that best-effort cancels the corresponding install on Infra
            (e.g. `lambda: cancel_service_install(server, api_key, name)`).
        description: What's being installed, for the interrupt message (e.g. "service 'ollama'").

    Returns:
        Whatever `call` returns.
    """
    try:
        return call()
    except KeyboardInterrupt:
        echo.warning(f"Interrupted; cancelling {description} install on Infra...")
        try:
            cancel()
        except Exception as exc:  # cancel() must never replace the KeyboardInterrupt raised below
            echo.warning(f"Could not cancel {description} install on Infra; it may still be running there. ({exc})")
        raise


def _error_message(response: httpx.Response, default_error_msg: str) -> str:
    """Extract a user-facing message from an error response.

    Prefers the ``{"error": {"message": ...}}`` field, falling back to the FastAPI
    ``{"detail": ...}`` field, then the raw response body, and finally to ``default_error_msg``.

    Args:
        response: The error response carried by the ``httpx.HTTPStatusError``.
        default_error_msg: Message used when the body is empty.

    Returns:
        The message to display to the user.
    """
    try:
        body = response.json()
        error = body.get("error") or {}
        message = error.get("message") if isinstance(error.get("message"), str) else None
        if message is None and isinstance(body.get("detail"), str):
            message = body.get("detail")
    except (JSONDecodeError, AttributeError):
        message = response.text

    return message or default_error_msg
