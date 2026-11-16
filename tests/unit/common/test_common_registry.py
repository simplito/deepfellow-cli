# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from unittest import mock
from unittest.mock import Mock

import httpx
import pytest
import typer

from deepfellow.common.registry import (
    _image_tag,
    _parse_tag,
    assert_cli_compatible,
    assert_not_downgrade,
    get_newest_image_tag,
    list_image_tags,
    newest_semver_tag,
    resolve_install_image,
    split_release_tag,
    warn_version_check_skipped,
)
from deepfellow.common.version import compatible_tags

pytestmark = pytest.mark.usefixtures("_unversioned_cli")

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


# --- split_release_tag ---


def test_split_release_tag_separates_version_and_suffix() -> None:
    assert split_release_tag("v2.3.0-volta") == ((2, 3, 0), "-volta")


def test_split_release_tag_plain_release_has_empty_suffix() -> None:
    assert split_release_tag("0.11.0") == ((0, 11, 0), "")


def test_split_release_tag_returns_none_for_non_release() -> None:
    assert split_release_tag("server-b1234") is None


# --- newest_semver_tag ---


def test_newest_semver_tag_ignores_variants_and_non_release_tags() -> None:
    tags = ["latest", "v2.3.0-volta", "v2.10.0", "v2.9.0"]

    assert newest_semver_tag(tags) == "v2.10.0"


def test_newest_semver_tag_returns_none_without_release_tags() -> None:
    assert newest_semver_tag(["latest", "dev"]) is None


def test_newest_semver_tag_returns_none_when_only_suffixed_tags_exist() -> None:
    assert newest_semver_tag(["v0.5.1-cu128", "v0.5.2-cu128"]) is None


def test_newest_semver_tag_picks_newest_within_suffix_family() -> None:
    tags = ["v0.5.2-cu128", "v0.5.1-cu128", "v0.5.3-cu126", "v0.6.0"]

    assert newest_semver_tag(tags, "-cu128") == "v0.5.2-cu128"


def test_newest_semver_tag_does_not_pick_prerelease_for_plain_releases() -> None:
    assert newest_semver_tag(["v2.5.0-rc1", "v2.4.0"]) == "v2.4.0"


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


@mock.patch("deepfellow.common.registry.echo")
@mock.patch("deepfellow.common.registry.httpx.get")
def test_get_newest_image_tag_exits_on_http_error(mock_get: Mock, mock_echo: Mock) -> None:
    mock_get.side_effect = httpx.ConnectError("unreachable")

    with pytest.raises(typer.Exit):
        get_newest_image_tag(HUB)

    assert mock_echo.error.call_count == 1
    assert f"--image {HUB}:X.Y.Z" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.common.registry.echo")
@mock.patch("deepfellow.common.registry.httpx.get")
def test_get_newest_image_tag_exits_when_registry_has_no_release_tags(mock_get: Mock, mock_echo: Mock) -> None:
    mock_get.side_effect = [
        _make_probe_response("https://auth.example.com/token"),
        _make_token_response("tok"),
        _make_tags_response(["latest", "abc123def"]),
    ]

    with pytest.raises(typer.Exit):
        get_newest_image_tag(HUB)

    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.common.registry.echo")
@mock.patch("deepfellow.common.registry.httpx.get")
def test_get_newest_image_tag_exits_when_token_missing(mock_get: Mock, mock_echo: Mock) -> None:
    probe = Mock(spec=httpx.Response)
    probe.status_code = 401
    probe.headers = {}  # no WWW-Authenticate -> no token -> list_image_tags returns []
    mock_get.return_value = probe

    with pytest.raises(typer.Exit):
        get_newest_image_tag(HUB)

    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.common.registry.httpx.get")
def test_get_newest_image_tag_omits_service_param_when_missing_from_header(mock_get: Mock) -> None:
    probe = Mock(spec=httpx.Response)
    probe.status_code = 401
    probe.headers = {"www-authenticate": 'Bearer realm="https://auth.example.com/token"'}
    mock_get.side_effect = [
        probe,
        _make_token_response("tok"),
        _make_tags_response(["0.25.0"]),
    ]

    result = get_newest_image_tag(HUB)

    assert result == f"{HUB}:0.25.0"
    assert mock_get.call_args_list[1] == mock.call(
        "https://auth.example.com/token",
        params={"scope": f"repository:{IMAGE_PATH}:pull"},
        timeout=10,
    )


# --- list_image_tags ---


@mock.patch("deepfellow.common.registry.httpx.get")
def test_list_image_tags_returns_semver_first_then_others_sorted(mock_get: Mock) -> None:
    mock_get.side_effect = [
        _make_probe_response("https://auth.example.com/token"),
        _make_token_response("tok"),
        _make_tags_response(["0.24.0", "v0.27.0", "0.25.0", "latest", "abc123"]),
    ]

    result = list_image_tags(HUB)

    assert result == ["v0.27.0", "0.25.0", "0.24.0", "abc123", "latest"]


@mock.patch("deepfellow.common.registry.httpx.get")
def test_list_image_tags_returns_empty_list_on_connection_error(mock_get: Mock) -> None:
    mock_get.side_effect = httpx.ConnectError("unreachable")

    result = list_image_tags(HUB)

    assert result == []


@mock.patch("deepfellow.common.registry.httpx.get")
def test_list_image_tags_returns_empty_list_when_token_missing(mock_get: Mock) -> None:
    probe = Mock(spec=httpx.Response)
    probe.status_code = 401
    probe.headers = {}
    mock_get.return_value = probe

    result = list_image_tags(HUB)

    assert result == []


def test_list_image_tags_returns_empty_list_for_host_less_image_name() -> None:
    result = list_image_tags("nginx")

    assert result == []


@mock.patch("deepfellow.common.registry.echo")
@mock.patch("deepfellow.common.registry.httpx.get")
def test_get_newest_image_tag_exits_when_tags_request_raises(mock_get: Mock, mock_echo: Mock) -> None:
    tags_resp = Mock(spec=httpx.Response)
    tags_resp.raise_for_status.side_effect = httpx.HTTPStatusError("403", request=Mock(), response=Mock())
    mock_get.side_effect = [
        _make_probe_response("https://auth.example.com/token"),
        _make_token_response("tok"),
        tags_resp,
    ]

    with pytest.raises(typer.Exit):
        get_newest_image_tag(HUB)

    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.common.version.cli_version", return_value="1.4.2")
@mock.patch("deepfellow.common.registry.httpx.get")
def test_get_newest_image_tag_skips_releases_newer_than_cli(mock_get: Mock, mock_cli_version: Mock) -> None:
    mock_get.side_effect = [
        _make_probe_response("https://auth.example.com/token"),
        _make_token_response("tok"),
        _make_tags_response(["1.3.9", "1.4.7", "1.5.0", "2.0.0"]),
    ]

    result = get_newest_image_tag(HUB)

    assert result == f"{HUB}:1.4.7"


@mock.patch("deepfellow.common.version.cli_version", return_value="1.4.2")
@mock.patch("deepfellow.common.registry.httpx.get")
def test_get_newest_image_tag_exits_when_no_release_fits_cli(mock_get: Mock, mock_cli_version: Mock) -> None:
    mock_get.side_effect = [
        _make_probe_response("https://auth.example.com/token"),
        _make_token_response("tok"),
        _make_tags_response(["2.0.0", "2.1.0"]),
    ]

    with pytest.raises(typer.Exit):
        get_newest_image_tag(HUB)


@pytest.mark.parametrize(
    "image",
    [
        pytest.param(f"{HUB}:1.5.0", id="newer-minor"),
        pytest.param(f"{HUB}:2.0.0", id="newer-major"),
        pytest.param(f"{HUB}:v1.5.0", id="newer-minor-v-prefix"),
        pytest.param(f"{HUB}:0.9.0", id="older-major"),
        pytest.param(f"{HUB}:1.5.0@sha256:abc", id="newer-minor-with-digest"),
        pytest.param(f"{HUB}:dev", id="non-version-tag"),
        pytest.param(f"{HUB}:latest", id="latest-tag"),
        pytest.param(HUB, id="no-tag"),
        pytest.param("localhost:5000/image", id="registry-port-no-tag"),
        pytest.param(f"{HUB}@sha256:abc", id="digest-only"),
        pytest.param(f"{HUB}:1.4.0@sha256:abc", id="matching-tag-with-digest"),
    ],
)
@mock.patch("deepfellow.common.registry.echo")
@mock.patch("deepfellow.common.version.cli_version", return_value="1.4.2")
def test_assert_cli_compatible_exits_when_image_not_known_to_work(
    mock_cli_version: Mock, mock_echo: Mock, image: str
) -> None:
    with pytest.raises(typer.Exit):
        assert_cli_compatible("Server", image)

    assert mock_echo.error.call_count == 1
    assert "--skip-version-check" in mock_echo.error.call_args.args[0]


@pytest.mark.parametrize(
    "image",
    [
        pytest.param(f"{HUB}:1.4.0", id="older-minor"),
        pytest.param(f"{HUB}:v1.4.9", id="same-minor-v-prefix"),
        pytest.param("localhost:5000/image:1.4.1", id="registry-port-and-tag"),
    ],
)
@mock.patch("deepfellow.common.version.cli_version", return_value="1.4.2")
def test_assert_cli_compatible_passes_when_image_fits_cli(mock_cli_version: Mock, image: str) -> None:
    assert_cli_compatible("Server", image)


@pytest.mark.parametrize(
    "image",
    [
        pytest.param(f"{HUB}:2.0.0", id="newer-major"),
        pytest.param(f"{HUB}:dev", id="non-version-tag"),
        pytest.param(HUB, id="no-tag"),
    ],
)
@mock.patch("deepfellow.common.version.cli_version", return_value="unknown")
def test_assert_cli_compatible_passes_any_image_for_dev_build_of_cli(mock_cli_version: Mock, image: str) -> None:
    assert_cli_compatible("Server", image)


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        pytest.param(f"{HUB}:1.2.3", "1.2.3", id="tag"),
        pytest.param(f"{HUB}:1.2.3@sha256:abc", "1.2.3", id="tag-and-digest"),
        pytest.param(f"{HUB}@sha256:abc", None, id="digest-only"),
        pytest.param(HUB, None, id="no-tag"),
        pytest.param("localhost:5000/image", None, id="registry-port-no-tag"),
        pytest.param("localhost:5000/image:dev", "dev", id="registry-port-and-tag"),
        pytest.param("image:", None, id="empty-tag"),
    ],
)
def test_image_tag_reads_tag_of_last_path_segment(image: str, expected: str | None) -> None:
    result = _image_tag(image)

    assert result == expected


@mock.patch("deepfellow.common.version.cli_version")
def test_compatible_tags_resolves_cli_version_once(mock_cli_version: Mock) -> None:
    mock_cli_version.return_value = "1.4.2"

    result = compatible_tags(["2.0.0", "1.5.0", "1.4.7", "1.3.9"])

    assert result == ["1.4.7", "1.3.9"]
    assert mock_cli_version.call_count == 1


@pytest.mark.parametrize(
    ("current", "newest"),
    [
        pytest.param(f"{HUB}:1.5.0", f"{HUB}:1.4.7", id="installed-newer"),
        pytest.param(f"{HUB}:v1.5.0", f"{HUB}:1.4.7", id="installed-newer-v-prefix"),
    ],
)
@mock.patch("deepfellow.common.version.cli_version", return_value="1.4.2")
def test_assert_not_downgrade_exits_when_newest_is_older(mock_cli_version: Mock, current: str, newest: str) -> None:
    with pytest.raises(typer.Exit):
        assert_not_downgrade("Server", current, newest)


@pytest.mark.parametrize(
    ("current", "newest"),
    [
        pytest.param(f"{HUB}:1.4.7", f"{HUB}:1.4.7", id="same"),
        pytest.param(f"{HUB}:1.4.0", f"{HUB}:1.4.7", id="installed-older"),
        pytest.param(f"{HUB}:latest", f"{HUB}:1.4.7", id="installed-not-a-version"),
        pytest.param("", f"{HUB}:1.4.7", id="nothing-installed"),
        pytest.param(f"{HUB}:1.5.0", f"{HUB}:latest", id="newest-not-a-version"),
    ],
)
@mock.patch("deepfellow.common.version.cli_version", return_value="1.4.2")
def test_assert_not_downgrade_passes_when_newest_is_not_older(
    mock_cli_version: Mock, current: str, newest: str
) -> None:
    assert_not_downgrade("Server", current, newest)


@pytest.mark.parametrize(
    ("cli", "tag", "expected_hint"),
    [
        pytest.param("0.37.1", "0.38.0", "deepfellow cli update", id="0x-newer-minor"),
        pytest.param("0.37.1", "0.36.4", "release that matches the CLI", id="0x-older-minor"),
        pytest.param("1.4.2", "2.0.0", "deepfellow cli update", id="newer-major"),
        pytest.param("1.4.2", "0.9.0", "release that matches the CLI", id="older-major"),
    ],
)
@mock.patch("deepfellow.common.registry.echo")
@mock.patch("deepfellow.common.version.cli_version")
def test_assert_cli_compatible_hint_depends_on_direction(
    mock_version_cli: Mock, mock_echo: Mock, cli: str, tag: str, expected_hint: str
) -> None:
    mock_version_cli.return_value = cli

    with pytest.raises(typer.Exit):
        assert_cli_compatible("Server", f"{HUB}:{tag}")

    assert expected_hint in mock_echo.error.call_args.args[0]


# --- warn_version_check_skipped / resolve_install_image ---


@mock.patch("deepfellow.common.registry.echo")
def test_warn_version_check_skipped_warns_about_the_flag(mock_echo: Mock) -> None:
    warn_version_check_skipped()

    assert mock_echo.warning.call_count == 1
    assert "--skip-version-check" in mock_echo.warning.call_args.args[0]


@mock.patch("deepfellow.common.registry.get_newest_image_tag", return_value=f"{HUB}:1.4.7")
def test_resolve_install_image_returns_newest_tag_for_default_image(mock_newest: Mock) -> None:
    result = resolve_install_image("Server", HUB, None, False, False)

    assert result == f"{HUB}:1.4.7"
    assert mock_newest.call_args == mock.call(HUB)


@mock.patch("deepfellow.common.registry.assert_cli_compatible")
@mock.patch("deepfellow.common.registry.get_newest_image_tag")
def test_resolve_install_image_checks_nothing_for_local_image(mock_newest: Mock, mock_assert: Mock) -> None:
    result = resolve_install_image("Server", HUB, f"{HUB}:dev-build", True, False)

    assert result == f"{HUB}:dev-build"
    assert mock_newest.call_count == 0
    assert mock_assert.call_count == 0


@mock.patch("deepfellow.common.registry.assert_cli_compatible")
@mock.patch("deepfellow.common.registry.get_newest_image_tag")
def test_resolve_install_image_checks_explicit_image(mock_newest: Mock, mock_assert: Mock) -> None:
    result = resolve_install_image("Server", HUB, f"{HUB}:1.4.0", False, False)

    assert result == f"{HUB}:1.4.0"
    assert mock_newest.call_count == 0
    assert mock_assert.call_args == mock.call("Server", f"{HUB}:1.4.0")


@mock.patch("deepfellow.common.registry.echo")
@mock.patch("deepfellow.common.registry.assert_cli_compatible")
def test_resolve_install_image_warns_instead_of_checking_when_skipped(mock_assert: Mock, mock_echo: Mock) -> None:
    result = resolve_install_image("Server", HUB, f"{HUB}:2.0.0", False, True)

    assert result == f"{HUB}:2.0.0"
    assert mock_assert.call_count == 0
    assert mock_echo.warning.call_count == 1


@pytest.mark.parametrize("image", [None, HUB, f"{HUB}@sha256:{'a' * 64}"])
@mock.patch("deepfellow.common.registry.echo")
def test_resolve_install_image_exits_for_local_image_without_tag(mock_echo: Mock, image: str | None) -> None:
    with pytest.raises(typer.Exit):
        resolve_install_image("Server", HUB, image, True, False)

    assert "--local-image" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.common.registry.echo")
def test_resolve_install_image_local_image_error_names_component_and_caller_flags(mock_echo: Mock) -> None:
    with pytest.raises(typer.Exit):
        resolve_install_image("Infra", HUB, None, True, False, "--infra-local-image", "--infra-image")

    message = mock_echo.error.call_args.args[0]
    assert message.startswith("Infra: `--infra-local-image` needs an explicit image tag")
    assert "`--infra-image <name>:<tag>`" in message


@mock.patch("deepfellow.common.registry.echo")
def test_resolve_install_image_server_local_image_error_names_component_and_caller_flags(mock_echo: Mock) -> None:
    with pytest.raises(typer.Exit):
        resolve_install_image("Server", HUB, "srv", True, False, "--server-local-image", "--server-image")

    message = mock_echo.error.call_args.args[0]
    assert message.startswith("Server: `--server-local-image` needs an explicit image tag")
    assert "`--server-image <name>:<tag>`" in message
    assert "--infra" not in message
