# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared Docker image registry utilities."""

import re

import httpx

from deepfellow.common.echo import echo


def _parse_tag(tag: str) -> tuple[int, ...] | None:
    """Return (major, minor, patch) for tags like 1.2.3 or v1.2.3, else None."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag)
    return tuple(int(x) for x in match.groups()) if match else None


def _get_registry_token(registry: str, image_path: str) -> str | None:
    """Obtain an anonymous bearer token via the registry's WWW-Authenticate realm."""
    try:
        probe = httpx.get(f"https://{registry}/v2/", timeout=10)
        www_auth = probe.headers.get("www-authenticate", "")
        # parse: Bearer realm="...",service="...",scope="..."
        realm_match = re.search(r'realm="([^"]+)"', www_auth)
        service_match = re.search(r'service="([^"]+)"', www_auth)
        if not realm_match:
            echo.debug(f"registry auth: no WWW-Authenticate realm from {registry}")
            return None
        realm = realm_match.group(1)
        service = service_match.group(1) if service_match else ""
        params = {"scope": f"repository:{image_path}:pull"}
        if service:
            params["service"] = service
        token_resp = httpx.get(realm, params=params, timeout=10)
        token_resp.raise_for_status()
        data = token_resp.json()
        return data.get("token") or data.get("access_token")
    except Exception as exc:
        echo.debug(f"registry auth failed for {registry}: {exc}")
        return None


def list_image_tags(hub: str) -> list[str]:
    """Return the image's available tags from the registry, newest semver first.

    Args:
        hub: Image hub without tag, e.g. ``registry.example.com/org/image``.

    Returns an empty list if the registry is unreachable, anonymous auth fails, or it reports no
    tags at all - never raises, since this is used to offer choices, not required data.
    """
    parts = hub.split("/", 1)
    if len(parts) != 2:
        echo.debug(f"registry: cannot parse hub '{hub}' - no registry/path separator")
        return []
    registry, image_path = parts

    token = _get_registry_token(registry, image_path)
    if not token:
        echo.debug(f"registry auth: no token obtained for {hub}")
        return []

    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = httpx.get(
            f"https://{registry}/v2/{image_path}/tags/list",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        raw_tags: list[str] = resp.json().get("tags") or []
    except Exception as exc:
        echo.debug(f"registry tags request failed for {hub}: {exc}")
        return []

    semver_tags = sorted((t for t in raw_tags if _parse_tag(t)), key=lambda v: _parse_tag(v) or (0, 0, 0), reverse=True)
    other_tags = sorted(t for t in raw_tags if not _parse_tag(t))
    return semver_tags + other_tags


def get_newest_image_tag(hub: str) -> str:
    """Return the full image reference with the newest semver tag from the registry.

    Args:
        hub: Image hub without tag, e.g. ``registry.example.com/org/image``.

    Falls back to :latest if the registry is unreachable or has no semver tags.
    """
    tags = list_image_tags(hub)
    semver_tags = [t for t in tags if _parse_tag(t)]
    if not semver_tags:
        if not tags:
            echo.warning(f"Unable to fetch tags for {hub}, falling back to latest.")
        return f"{hub}:latest"

    return f"{hub}:{semver_tags[0]}"
