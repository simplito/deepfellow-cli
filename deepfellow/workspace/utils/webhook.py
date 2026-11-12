# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Set up DeepFellow Server notifications (webhooks) for Workspace."""

import ipaddress
import secrets
import socket
from collections.abc import Mapping, MutableMapping
from typing import Any
from urllib.parse import urlencode, urlparse

import typer

from deepfellow.common.config import read_env_file
from deepfellow.common.echo import echo
from deepfellow.common.rest import check_health, delete, get_server_url, make_request, post
from deepfellow.common.rest import get as rest_get
from deepfellow.common.state import state
from deepfellow.server.utils.login import get_token
from deepfellow.workspace.utils.public_url import is_loopback_host

WEBHOOK_PATH = "/webhooks/df-server"
WEBHOOK_SECRET_KEY = "DF_SERVER_WEBHOOK_SECRET"
_ORGANIZATION_ID_KEY = "DF_SERVER_ORGANIZATION_ID"
_PROJECT_ID_KEY = "DF_SERVER_PROJECT_ID"
_SECRET_BYTES = 32
_PAGE_SIZE = 100
NO_WEBHOOK_WARNING = (
    "Without a public https:// address DeepFellow Server cannot notify Workspace when files finish indexing, "
    "so indexing files in Workspace will not be fully working. Reinstall with --public-url set to an https:// "
    "address reachable from DeepFellow Server to enable it."
)

Passed = MutableMapping[str, str | None]


def _parse_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse an IP literal, including the legacy IPv4 forms (`127.1`, `0x7f.1`, `2130706433`) that Server reads too."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    try:
        return ipaddress.IPv4Address(socket.inet_aton(host))
    except (OSError, ValueError):
        return None


def is_public_https(url: str) -> bool:
    """Tell whether DeepFellow Server would accept `url` as a webhook target, following its own rule.

    Server requires https and refuses `localhost`, `*.localhost` and non-public IP literals (also legacy forms such
    as `127.1`). A host name is not resolved, so any other name is accepted, including internal ones.

    Args:
        url: The Workspace address.

    Returns:
        `True` for an `https://` address that is not loopback and not a private or reserved IP.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").rstrip(".")
    if parsed.scheme != "https" or not host or is_loopback_host(host):
        return False
    ip = _parse_ip(host)
    return ip is None or ip.is_global


def webhook_url(public_url: str) -> str:
    """Build the address DeepFellow Server delivers notifications to.

    Args:
        public_url: The Workspace address.

    Returns:
        The Workspace webhook endpoint under that address.
    """
    return f"{public_url.rstrip('/')}{WEBHOOK_PATH}"


def _find_endpoint(server: str, token: str, headers: dict[str, str], project_id: str, url: str) -> str | None:
    """Find the id of the project's webhook endpoint that delivers to `url`, going through all pages."""
    base = f"{server}/v1/organization/projects/{project_id}/webhooks"
    after: str | None = None
    while True:
        query = urlencode({"limit": _PAGE_SIZE} | ({"after": after} if after else {}))
        page = rest_get(
            f"{base}?{query}",
            token,
            headers=headers,
            item_name="Webhook endpoints API (DeepFellow Server may be too old to support it)",
        )
        items: list[dict[str, Any]] = page.get("data") or []
        for item in items:
            if item.get("url") == url and item.get("id"):
                return str(item["id"])
        last_id = page.get("last_id")
        if not page.get("has_more") or not last_id:
            return None
        after = str(last_id)


def _register(server: str, token: str, organization_id: str, project_id: str, url: str, secret: str) -> None:
    """Create the webhook endpoint in the project, or set the secret on the one that already has this address."""
    headers = {"OpenAI-Organization": organization_id}
    base = f"{server}/v1/organization/projects/{project_id}/webhooks"
    endpoint_id = _find_endpoint(server, token, headers, project_id, url)
    if endpoint_id is None:
        post(base, token, headers=headers, item_name="webhook endpoint", data={"url": url, "secret": secret})
        return
    make_request(
        "PUT",
        f"{base}/{endpoint_id}",
        token,
        headers=headers,
        data={"secret": secret},
        err_msg="Unable to update the webhook endpoint.",
    )


def _remove_old_endpoint(server: str, token: str, organization_id: str, project_id: str, old_url: str) -> None:
    """Offer to delete the project's webhook endpoint for the address Workspace no longer uses."""
    headers = {"OpenAI-Organization": organization_id}
    endpoint_id = _find_endpoint(server, token, headers, project_id, old_url)
    if endpoint_id is None:
        return
    if echo.confirm(
        f"DeepFellow Server still notifies the previous address {old_url}. Remove that endpoint?", ignore_yes=True
    ):
        delete(
            f"{server}/v1/organization/projects/{project_id}/webhooks/{endpoint_id}",
            token,
            headers=headers,
            item_name="webhook endpoint",
        )


def _workspace_server_url(passed: Passed, existing: Mapping[str, str]) -> str | None:
    """Return the DeepFellow Server address Workspace talks to, without the `/v1` suffix, if it is known."""
    url = passed.get("DF_SERVER_URL") or existing.get("DF_SERVER_URL")
    if not url:
        return None
    url = url.rstrip("/")
    return url.removesuffix("/v1").rstrip("/")


def _has_stored_login() -> bool:
    """Tell whether the CLI secrets file holds a Server access token."""
    secrets_file = state.cli_secrets_file
    return secrets_file.is_file() and bool(read_env_file(secrets_file).get("DF_USER_TOKEN"))


def configure_webhook(passed: Passed, existing: Mapping[str, str], public_url: str) -> None:
    """Make DeepFellow Server notify Workspace about finished file indexing, when the address allows it.

    Needs an organization admin of DeepFellow Server (the CLI login is used). The secret is generated on the first
    run and kept from the previous install afterwards; it is stored in `passed` only when Server has accepted it,
    so Workspace never gets a secret Server does not know. A failure is reported, but does not stop the install.

    Args:
        passed: Values given explicitly; the secret is stored in it.
        existing: The .env of a previous install (empty on a fresh install).
        public_url: The Workspace address that will be written.
    """
    if not is_public_https(public_url):
        echo.warning(NO_WEBHOOK_WARNING)
        old_public_url = existing.get("PUBLIC_URL")
        if old_public_url and is_public_https(old_public_url):
            echo.warning(
                f"DeepFellow Server may still notify the previous address {old_public_url}, and the old secret stays "
                "in .env. Remove that webhook endpoint in DeepFellow Server."
            )
        return
    organization_id = passed.get(_ORGANIZATION_ID_KEY) or existing.get(_ORGANIZATION_ID_KEY)
    project_id = passed.get(_PROJECT_ID_KEY) or existing.get(_PROJECT_ID_KEY)
    if not organization_id or not project_id:
        echo.warning(
            "The organization and project ids are not known, so DeepFellow Server notifications were not set up. "
            "Give them with --df-server-organization-id and --df-server-project-id."
        )
        return
    if state.yes and not _has_stored_login():
        echo.warning(
            "DeepFellow Server notifications were not set up: --yes cannot sign in as an organization admin and "
            "no CLI login is stored. Run `df server login` and reinstall, or reinstall without --yes."
        )
        return
    secret = passed.get(WEBHOOK_SECRET_KEY) or existing.get(WEBHOOK_SECRET_KEY) or secrets.token_urlsafe(_SECRET_BYTES)
    url = webhook_url(public_url)
    echo.info("Setting up DeepFellow Server notifications for Workspace (requires an organization admin login).")
    try:
        workspace_server = _workspace_server_url(passed, existing)
        if state.yes and workspace_server:
            # --yes keeps the CLI default Server; the Workspace's Server is only used here.
            check_health(workspace_server)
            server = workspace_server
        else:
            server = get_server_url(workspace_server)
        echo.info(f"Using DeepFellow Server {server}. Signing in there replaces the stored CLI login.")
        token = get_token(state.cli_secrets_file, server)
        _register(server, token, organization_id, project_id, url, secret)
    except (typer.Exit, ValueError, KeyError):
        echo.warning(
            "DeepFellow Server notifications were not set up, so indexing files in Workspace will not be fully "
            "working. Fix the problem above and reinstall to try again."
        )
        return
    passed[WEBHOOK_SECRET_KEY] = secret
    echo.info(f"DeepFellow Server will notify Workspace at {url}.")
    old_public_url = existing.get("PUBLIC_URL")
    if old_public_url and is_public_https(old_public_url) and webhook_url(old_public_url) != url:
        try:
            _remove_old_endpoint(server, token, organization_id, project_id, webhook_url(old_public_url))
        except (typer.Exit, ValueError, KeyError):
            echo.warning("The endpoint for the previous address was not removed; remove it in DeepFellow Server.")
