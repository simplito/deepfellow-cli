# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Infra image registry utilities."""

import re

import httpx

from deepfellow.common.defaults import DF_INFRA_IMAGE_HUB


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
    except Exception:
        return None


def get_newest_image_tag() -> str:
    """Return the full image reference with the newest semver tag from the registry.

    Falls back to :latest if the registry is unreachable.
    """
    hub = DF_INFRA_IMAGE_HUB
    registry, image_path = hub.split("/", 1)

    token = _get_registry_token(registry, image_path)
    if not token:
        return f"{hub}:latest"

    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = httpx.get(
            f"https://{registry}/v2/{image_path}/tags/list",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        raw_tags: list[str] = resp.json().get("tags") or []
    except Exception:
        return f"{hub}:latest"

    semver_tags = [t for t in raw_tags if _parse_tag(t)]
    if not semver_tags:
        return f"{hub}:latest"

    newest = max(semver_tags, key=lambda v: _parse_tag(v) or (0, 0, 0))
    return f"{hub}:{newest}"
