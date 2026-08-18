# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Infra connection resolution utilities."""

from collections.abc import Callable
from json import JSONDecodeError
from typing import Any, cast

import httpx
import typer

from deepfellow.common.config import read_env_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.exceptions import InfraInstallSkippedError
from deepfellow.common.state import state
from deepfellow.common.validation import validate_url


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
) -> dict[str, Any]:
    """Call the Infra API, translating transport errors into user-facing messages.

    ``request`` must invoke the REST helper with ``reraise=True`` so ``httpx`` errors
    propagate here instead of being swallowed with a generic message.

    Args:
        request: Zero-argument callable performing the REST call (e.g. ``lambda: get(...)``).
        default_error_msg: Message shown when an HTTP error response has no body.
        server: If given (together with `api_key`), persisted via `persist_infra_connection`
            once `request` succeeds — never before, so a bad `server`/`api_key` never clobbers
            a previously working local config.
        api_key: See `server`.
        quiet: Forwarded to `persist_infra_connection` — see there.
        skip_if_message_contains: When the error message extracted from an ``httpx.HTTPStatusError``
            response contains this substring, raise ``InfraInstallSkippedError`` instead of echoing an
            error and exiting — lets the caller treat it as a no-op.

    Returns:
        The parsed JSON response.

    Raises:
        InfraInstallSkippedError: if the extracted error message matches `skip_if_message_contains`.
    """
    try:
        result = request()
    except httpx.ConnectError as exc:
        echo.error("No connection with DeepFellow Infra. Is it up? (deepfellow infra start)")
        raise typer.Exit(1) from exc
    except httpx.HTTPStatusError as exc:
        message = _error_message(exc.response, default_error_msg)
        if skip_if_message_contains and skip_if_message_contains in message:
            raise InfraInstallSkippedError(message) from exc
        echo.error(message)
        raise typer.Exit(1) from exc
    except httpx.HTTPError as exc:
        echo.error(default_error_msg)
        raise typer.Exit(1) from exc

    if server is not None and api_key is not None:
        persist_infra_connection(server, api_key, quiet=quiet)

    return result


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
