# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest import mock
from unittest.mock import Mock

import httpx

from deepfellow.common.registry import _parse_tag, get_newest_image_tag

HUB = "hub.example.com/org/image"
IMAGE_PATH = "org/image"


# --- _parse_tag ---


def test_parse_tag_plain() -> None:
    assert _parse_tag("0.25.0") == (0, 25, 0)


def test_parse_tag_with_v_prefix() -> None:
    assert _parse_tag("v0.27.0") == (0, 27, 0)


def test_parse_tag_returns_none_for_sha() -> None:
    assert _parse_tag("ace593ea6b67733ea537a2af4fb8f687") is None


def test_parse_tag_returns_none_for_latest() -> None:
    assert _parse_tag("latest") is None


def test_parse_tag_returns_none_for_partial() -> None:
    assert _parse_tag("0.25") is None


# --- get_newest_image_tag ---


def _make_probe_response(realm: str, service: str = "Docker registry") -> Mock:
    resp = Mock(spec=httpx.Response)
    resp.status_code = 401
    resp.headers = {"www-authenticate": f'Bearer realm="{realm}",service="{service}"'}
    return resp


def _make_token_response(token: str) -> Mock:
    resp = Mock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"token": token}
    resp.raise_for_status = Mock()
    return resp


def _make_tags_response(tags: list[str]) -> Mock:
    resp = Mock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"name": IMAGE_PATH, "tags": tags}
    resp.raise_for_status = Mock()
    return resp


@mock.patch("deepfellow.common.registry.httpx.get")
def test_get_newest_image_tag_returns_highest_semver(mock_get: Mock) -> None:
    mock_get.side_effect = [
        _make_probe_response("https://auth.example.com/token"),
        _make_token_response("tok"),
        _make_tags_response(["0.24.0", "v0.27.0", "0.25.0", "latest", "abc123"]),
    ]

    result = get_newest_image_tag(HUB)

    assert result == f"{HUB}:v0.27.0"


@mock.patch("deepfellow.common.registry.httpx.get")
def test_get_newest_image_tag_plain_semver_beats_lower_v_tag(mock_get: Mock) -> None:
    mock_get.side_effect = [
        _make_probe_response("https://auth.example.com/token"),
        _make_token_response("tok"),
        _make_tags_response(["v0.26.0", "0.27.1"]),
    ]

    result = get_newest_image_tag(HUB)

    assert result == f"{HUB}:0.27.1"


@mock.patch("deepfellow.common.registry.httpx.get")
def test_get_newest_image_tag_falls_back_to_latest_on_http_error(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ConnectError("unreachable")

    result = get_newest_image_tag(HUB)

    assert result == f"{HUB}:latest"


@mock.patch("deepfellow.common.registry.httpx.get")
def test_get_newest_image_tag_falls_back_when_no_semver_tags(mock_get: Mock) -> None:
    mock_get.side_effect = [
        _make_probe_response("https://auth.example.com/token"),
        _make_token_response("tok"),
        _make_tags_response(["latest", "abc123def", "dev"]),
    ]

    result = get_newest_image_tag(HUB)

    assert result == f"{HUB}:latest"


@mock.patch("deepfellow.common.registry.httpx.get")
def test_get_newest_image_tag_falls_back_when_token_missing(mock_get: Mock) -> None:
    probe = Mock(spec=httpx.Response)
    probe.status_code = 401
    probe.headers = {}  # no WWW-Authenticate
    mock_get.return_value = probe

    result = get_newest_image_tag(HUB)

    assert result == f"{HUB}:latest"


@mock.patch("deepfellow.common.registry.httpx.get")
def test_get_newest_image_tag_falls_back_when_tags_request_raises(mock_get: Mock) -> None:
    tags_resp = Mock(spec=httpx.Response)
    tags_resp.raise_for_status.side_effect = httpx.HTTPStatusError("403", request=Mock(), response=Mock())
    mock_get.side_effect = [
        _make_probe_response("https://auth.example.com/token"),
        _make_token_response("tok"),
        tags_resp,
    ]

    result = get_newest_image_tag(HUB)

    assert result == f"{HUB}:latest"
