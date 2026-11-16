# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""The address browsers reach Workspace at, and the settings that depend on it."""

import ipaddress
import re
from collections.abc import Mapping, MutableMapping
from urllib.parse import urlparse

import typer

from deepfellow.common.echo import echo, is_interactive
from deepfellow.common.exceptions import InstallError
from deepfellow.common.state import state
from deepfellow.common.validation import validate_origin, validate_origins

PUBLIC_URL_KEY = "PUBLIC_URL"
TRUSTED_PROXY_KEY = "TRUSTED_PROXY_ENABLED"
# Extra origins the app trusts besides PUBLIC_URL, comma-separated.
TRUSTED_ORIGINS_KEY = "TRUSTED_ORIGINS"
DEFAULT_PUBLIC_URL_PATTERN = re.compile(r"http://localhost:\d+")

Passed = MutableMapping[str, str | None]


def is_loopback_host(host: str) -> bool:
    """Tell whether browsers treat `host` as this machine, where plain http still counts as secure.

    Args:
        host: Host name or IP address, without brackets.

    Returns:
        True for `localhost`, `*.localhost`, `127.0.0.0/8` and `::1`.
    """
    host = host.lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def insecure_context_warning(url: str) -> str | None:
    """Describe what will not work in the browser at `url`.

    Args:
        url: The Workspace address.

    Returns:
        The warning for plain http on a host other than localhost, otherwise `None`.
    """
    parsed = urlparse(url)
    if parsed.scheme != "http" or not parsed.hostname or is_loopback_host(parsed.hostname):
        return None
    return (
        f"Workspace will be opened at {url}. On http with an address other than localhost, browsers block some "
        "features, e.g. copying and adding attachments. Use https:// (behind a reverse proxy that terminates TLS) "
        "or http://localhost."
    )


def default_public_url(existing: Mapping[str, str], port: int) -> str:
    """Pick the address offered when none is given: the previous one, else `http://localhost:<port>`.

    A previous address of the default form follows a changed port, as the written .env does.

    Args:
        existing: The .env of a previous install (empty on a fresh install).
        port: Published Workspace port.

    Returns:
        The default address.
    """
    previous = existing.get(PUBLIC_URL_KEY)
    if previous and not DEFAULT_PUBLIC_URL_PATTERN.fullmatch(previous):
        return previous
    return f"http://localhost:{port}"


def _asks() -> bool:
    """Tell whether value questions are asked: interactive mode without --yes."""
    return is_interactive() and not state.yes


def resolve_public_url(passed: Passed, existing: Mapping[str, str], port: int) -> str:
    """Choose the Workspace address: the given one, else asked for, else the default.

    With --yes or --non-interactive nothing is asked and `passed` is left as is.

    Args:
        passed: Values given explicitly; an answer is stored in it.
        existing: The .env of a previous install (empty on a fresh install).
        port: Published Workspace port.

    Returns:
        The address that will be written.

    Raises:
        InstallError: When nothing is asked and the address kept from the previous install is not a valid origin.
    """
    if given := passed.get(PUBLIC_URL_KEY):
        return given
    default = default_public_url(existing, port)
    if _asks():
        answer: str = echo.prompt_until_valid(
            "Address Workspace is opened at in the browser", validate_origin, default=default
        )
        passed[PUBLIC_URL_KEY] = answer
        return answer
    try:
        default = validate_origin(default) or default
    except typer.BadParameter:
        raise InstallError(
            f"{PUBLIC_URL_KEY} kept from the existing installation ({default!r}) is not a valid origin; "
            "pass --public-url."
        ) from None
    return default


def apply_https_settings(passed: Passed, existing: Mapping[str, str], public_url: str) -> None:
    """Trust the reverse proxy in front of an https address and ask for extra trusted origins.

    Args:
        passed: Values given explicitly; updated in place. A `--trusted-proxy` / `--no-trusted-proxy` flag, and
            `TRUSTED_PROXY_ENABLED=false` kept from the previous install (`--no-trusted-proxy`), are kept.
        existing: The .env of a previous install (empty on a fresh install).
        public_url: The Workspace address that will be written.
    """
    if urlparse(public_url).scheme != "https":
        return
    if passed.get(TRUSTED_PROXY_KEY) is None and existing.get(TRUSTED_PROXY_KEY) != "false":
        passed[TRUSTED_PROXY_KEY] = "true"
        echo.info("The address is https, so the reverse proxy in front of Workspace is trusted (--trusted-proxy).")
    if passed.get(TRUSTED_ORIGINS_KEY) is not None or not _asks():
        return
    passed[TRUSTED_ORIGINS_KEY] = echo.prompt_until_valid(
        "Other trusted origins, comma-separated (optional)",
        validate_origins,
        default=existing.get(TRUSTED_ORIGINS_KEY),
    )
