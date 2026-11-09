# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Look up what DeepFellow Server knows about an API key."""

import httpx

from deepfellow.common.echo import echo
from deepfellow.common.state import state

_INFO_TIMEOUT_SECONDS = 5.0

# Servers (base URL, API key) that already failed in this run; they are not asked again and not warned about again.
_failed: set[tuple[str, str]] = set()


def _base(server_url: str) -> str:
    """Strip the trailing slash and `/v1` from a Server URL."""
    return server_url.rstrip("/").removesuffix("/v1")


def server_lookup_failed(server_url: str, api_key: str) -> bool:
    """Tell whether a lookup against this Server and API key already failed (and was already reported).

    Args:
        server_url: DeepFellow Server URL, with or without the trailing `/v1`.
        api_key: DeepFellow Server project API key.

    Returns:
        `True` when an earlier request failed.
    """
    return (_base(server_url), api_key) in _failed


def _get_json(server_url: str, api_key: str, path: str) -> object | None:
    """GET a JSON document from Server, with one availability check and one warning per Server and key.

    The URL meant for the container (e.g. `http://server:8000/v1`) often does not resolve on this host, so when it
    cannot be reached the host URL from the CLI config is tried too.

    Args:
        server_url: DeepFellow Server URL, with or without the trailing `/v1`.
        api_key: DeepFellow Server project API key.
        path: Path under the Server root, starting with `/`.

    Returns:
        The decoded JSON, or `None` when the request failed (reported once) or failed earlier.
    """
    base = _base(server_url)
    if (base, api_key) in _failed:
        return None
    bases = [base]
    host_url = state.cli_config.get("df_server_url")
    if isinstance(host_url, str) and host_url and _base(host_url) != base:
        bases.append(_base(host_url))
    first_error: tuple[str, Exception] | None = None  # the failure of the URL the user gave
    for candidate in bases:
        url = f"{candidate}{path}"
        echo.debug(f"GET {url}")
        try:
            response = httpx.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=_INFO_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, httpx.InvalidURL, ValueError) as exc:
            first_error = first_error or (url, exc)
            if not isinstance(exc, httpx.TransportError):
                break
    _failed.add((base, api_key))
    url, error = first_error  # type: ignore[misc]
    echo.warning(f"Request to DeepFellow Server failed (GET {url}): {_describe(error)}")
    return None


def _describe(exc: Exception) -> str:
    """Describe a failed Server request in one short phrase, with the cause the user can act on."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        hint = " - the API key was rejected" if status in (401, 403) else ""
        return f"HTTP {status}{hint}"
    if isinstance(exc, httpx.TimeoutException):
        return f"timed out after {_INFO_TIMEOUT_SECONDS:g}s"
    return str(exc) or type(exc).__name__


def resolve_server_ids(server_url: str, api_key: str) -> tuple[str, str] | None:
    """Ask DeepFellow Server which organization and project an API key belongs to.

    Args:
        server_url: DeepFellow Server URL, with or without the trailing `/v1`.
        api_key: DeepFellow Server project API key.

    Returns:
        The `(organization_id, project_id)` pair, or `None` when Server is unreachable, rejects the key,
        runs a version that does not report them, or the key has no project.
    """
    data = _get_json(server_url, api_key, "/info")
    organization_id = data.get("organization_id") if isinstance(data, dict) else None
    project_id = data.get("project_id") if isinstance(data, dict) else None
    if not isinstance(organization_id, str) or not isinstance(project_id, str):
        return None
    return organization_id, project_id


def _is_chat_model(item: dict[object, object]) -> bool:
    """Tell whether a `/v1/models` entry may serve as a chat model.

    Entries without a declared type (an older Server or Infra) are kept, since nothing says they are not chat models.
    """
    props = item.get("props")
    model_type = props.get("type") if isinstance(props, dict) else None
    if not isinstance(model_type, str) or not model_type:
        return True
    return model_type.split("-")[0] == "llm"


def list_server_models(server_url: str, api_key: str) -> list[str] | None:
    """Ask DeepFellow Server which chat models the project of an API key can use.

    Embedding, speech, rerank, decision, MCP and custom entries are left out, because the caller picks a chat model.

    Args:
        server_url: DeepFellow Server URL, with or without the trailing `/v1`.
        api_key: DeepFellow Server project API key.

    Returns:
        Model ids in the order Server reports them, or `None` when Server is unreachable, rejects the key,
        or answers in an unexpected shape.
    """
    data = _get_json(server_url, api_key, "/v1/models?additional_data=true")
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    ids = [
        item["id"]
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str) and _is_chat_model(item)
    ]
    return list(dict.fromkeys(ids))
