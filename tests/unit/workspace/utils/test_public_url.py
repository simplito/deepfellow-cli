# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.common.exceptions import InstallError
from deepfellow.common.validation import validate_origin, validate_origins
from deepfellow.workspace.utils.public_url import (
    apply_https_settings,
    default_public_url,
    insecure_context_warning,
    is_loopback_host,
    resolve_public_url,
)


@pytest.mark.parametrize("host", ["localhost", "LOCALHOST", "app.localhost", "127.0.0.1", "127.5.6.7", "::1"])
def test_is_loopback_host_recognises_loopback(host: str) -> None:
    assert is_loopback_host(host) is True


@pytest.mark.parametrize("host", ["192.168.1.10", "10.0.0.5", "workspace.lan", "localhost.example.com", "::2"])
def test_is_loopback_host_rejects_other_hosts(host: str) -> None:
    assert is_loopback_host(host) is False


@pytest.mark.parametrize("url", ["http://192.168.1.10:3000", "http://workspace.lan:3000", "http://10.0.0.5"])
def test_insecure_context_warning_http_on_other_host_warns(url: str) -> None:
    result = insecure_context_warning(url)

    assert result is not None
    assert url in result
    assert "copying" in result
    assert "https://" in result


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:3000",
        "http://app.localhost:3000",
        "http://127.0.0.1:3000",
        "http://[::1]:3000",
        "https://ws.example.com",
        "https://192.168.1.10",
    ],
)
def test_insecure_context_warning_secure_contexts_do_not_warn(url: str) -> None:
    assert insecure_context_warning(url) is None


def test_default_public_url_fresh_install_uses_localhost_and_port() -> None:
    assert default_public_url({}, 3000) == "http://localhost:3000"


def test_default_public_url_keeps_custom_previous_address() -> None:
    result = default_public_url({"PUBLIC_URL": "https://ws.example.com"}, 3000)

    assert result == "https://ws.example.com"


def test_default_public_url_default_form_follows_changed_port() -> None:
    result = default_public_url({"PUBLIC_URL": "http://localhost:3000"}, 8080)

    assert result == "http://localhost:8080"


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_resolve_public_url_flag_given_asks_nothing(mock_echo: Mock, mock_interactive: Mock) -> None:
    passed: dict[str, str | None] = {"PUBLIC_URL": "https://ws.example.com"}

    result = resolve_public_url(passed, {}, 3000)

    assert result == "https://ws.example.com"
    assert mock_echo.prompt_until_valid.call_count == 0


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_resolve_public_url_interactive_asks_with_default(mock_echo: Mock, mock_interactive: Mock) -> None:
    mock_echo.prompt_until_valid.return_value = "http://localhost:3000"
    passed: dict[str, str | None] = {"PUBLIC_URL": None}

    result = resolve_public_url(passed, {}, 3000)

    assert result == "http://localhost:3000"
    assert passed["PUBLIC_URL"] == "http://localhost:3000"
    assert mock_echo.prompt_until_valid.call_count == 1
    assert mock_echo.prompt_until_valid.call_args == mock.call(
        "Address Workspace is opened at in the browser", validate_origin, default="http://localhost:3000"
    )


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_resolve_public_url_reinstall_offers_previous_address(mock_echo: Mock, mock_interactive: Mock) -> None:
    mock_echo.prompt_until_valid.return_value = "https://other.example.com"
    passed: dict[str, str | None] = {"PUBLIC_URL": None}

    result = resolve_public_url(passed, {"PUBLIC_URL": "https://ws.example.com"}, 3000)

    assert result == "https://other.example.com"
    assert mock_echo.prompt_until_valid.call_args.kwargs["default"] == "https://ws.example.com"


@mock.patch("deepfellow.workspace.utils.public_url.state")
@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_resolve_public_url_yes_uses_previous_without_asking(
    mock_echo: Mock, mock_interactive: Mock, mock_state: Mock
) -> None:
    mock_state.yes = True
    passed: dict[str, str | None] = {"PUBLIC_URL": None}

    result = resolve_public_url(passed, {"PUBLIC_URL": "https://ws.example.com"}, 3000)

    assert result == "https://ws.example.com"
    assert passed["PUBLIC_URL"] is None
    assert mock_echo.prompt_until_valid.call_count == 0


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_resolve_public_url_non_interactive_uses_default_without_asking(
    mock_echo: Mock, mock_interactive: Mock
) -> None:
    passed: dict[str, str | None] = {"PUBLIC_URL": None}

    result = resolve_public_url(passed, {}, 8080)

    assert result == "http://localhost:8080"
    assert passed["PUBLIC_URL"] is None
    assert mock_echo.prompt_until_valid.call_count == 0


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_apply_https_settings_https_enables_proxy_trust(mock_echo: Mock, mock_interactive: Mock) -> None:
    passed: dict[str, str | None] = {"TRUSTED_PROXY_ENABLED": None, "TRUSTED_ORIGINS": None}

    apply_https_settings(passed, {}, "https://ws.example.com")

    assert passed["TRUSTED_PROXY_ENABLED"] == "true"
    assert passed["TRUSTED_ORIGINS"] is None
    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_echo.info.call_count == 1


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_apply_https_settings_explicit_opt_out_wins(mock_echo: Mock, mock_interactive: Mock) -> None:
    passed: dict[str, str | None] = {"TRUSTED_PROXY_ENABLED": "false", "TRUSTED_ORIGINS": None}

    apply_https_settings(passed, {}, "https://ws.example.com")

    assert passed["TRUSTED_PROXY_ENABLED"] == "false"


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_apply_https_settings_http_changes_nothing_and_asks_nothing(mock_echo: Mock, mock_interactive: Mock) -> None:
    passed: dict[str, str | None] = {"TRUSTED_PROXY_ENABLED": None, "TRUSTED_ORIGINS": None}

    apply_https_settings(passed, {}, "http://localhost:3000")

    assert passed == {"TRUSTED_PROXY_ENABLED": None, "TRUSTED_ORIGINS": None}
    assert mock_echo.prompt_until_valid.call_count == 0


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_apply_https_settings_interactive_asks_for_extra_origins(mock_echo: Mock, mock_interactive: Mock) -> None:
    mock_echo.prompt_until_valid.return_value = "https://a.example.com"
    passed: dict[str, str | None] = {"TRUSTED_PROXY_ENABLED": None, "TRUSTED_ORIGINS": None}

    apply_https_settings(passed, {}, "https://ws.example.com")

    assert passed["TRUSTED_ORIGINS"] == "https://a.example.com"
    assert mock_echo.prompt_until_valid.call_count == 1
    assert mock_echo.prompt_until_valid.call_args == mock.call(
        "Other trusted origins, comma-separated (optional)", validate_origins, default=None
    )


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_apply_https_settings_empty_answer_adds_none(mock_echo: Mock, mock_interactive: Mock) -> None:
    mock_echo.prompt_until_valid.return_value = None
    passed: dict[str, str | None] = {"TRUSTED_PROXY_ENABLED": None, "TRUSTED_ORIGINS": None}

    apply_https_settings(passed, {}, "https://ws.example.com")

    assert passed["TRUSTED_ORIGINS"] is None


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_apply_https_settings_reinstall_offers_previous_origins(mock_echo: Mock, mock_interactive: Mock) -> None:
    mock_echo.prompt_until_valid.return_value = "https://a.example.com"
    passed: dict[str, str | None] = {"TRUSTED_PROXY_ENABLED": None, "TRUSTED_ORIGINS": None}

    apply_https_settings(passed, {"TRUSTED_ORIGINS": "https://a.example.com"}, "https://ws.example.com")

    assert mock_echo.prompt_until_valid.call_args.kwargs["default"] == "https://a.example.com"


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_apply_https_settings_flag_given_asks_nothing(mock_echo: Mock, mock_interactive: Mock) -> None:
    passed: dict[str, str | None] = {"TRUSTED_PROXY_ENABLED": None, "TRUSTED_ORIGINS": "https://a.example.com"}

    apply_https_settings(passed, {}, "https://ws.example.com")

    assert passed["TRUSTED_ORIGINS"] == "https://a.example.com"
    assert mock_echo.prompt_until_valid.call_count == 0


@mock.patch("deepfellow.workspace.utils.public_url.state")
@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_apply_https_settings_yes_asks_nothing(mock_echo: Mock, mock_interactive: Mock, mock_state: Mock) -> None:
    mock_state.yes = True
    passed: dict[str, str | None] = {"TRUSTED_PROXY_ENABLED": None, "TRUSTED_ORIGINS": None}

    apply_https_settings(passed, {}, "https://ws.example.com")

    assert passed["TRUSTED_PROXY_ENABLED"] == "true"
    assert passed["TRUSTED_ORIGINS"] is None
    assert mock_echo.prompt_until_valid.call_count == 0


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_resolve_public_url_invalid_kept_address_raises(mock_echo: Mock, mock_interactive: Mock) -> None:
    passed: dict[str, str | None] = {"PUBLIC_URL": None}

    with pytest.raises(InstallError) as exc_info:
        resolve_public_url(passed, {"PUBLIC_URL": "not a url/path"}, 3000)

    assert "--public-url" in str(exc_info.value)


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_resolve_public_url_empty_kept_address_uses_default(mock_echo: Mock, mock_interactive: Mock) -> None:
    passed: dict[str, str | None] = {"PUBLIC_URL": None}

    result = resolve_public_url(passed, {"PUBLIC_URL": ""}, 3000)

    assert result == "http://localhost:3000"


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_resolve_public_url_kept_address_trailing_slash_is_stripped(mock_echo: Mock, mock_interactive: Mock) -> None:
    passed: dict[str, str | None] = {"PUBLIC_URL": None}

    result = resolve_public_url(passed, {"PUBLIC_URL": "https://ws.example.com/"}, 3000)

    assert result == "https://ws.example.com"


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_apply_https_settings_keeps_proxy_trust_switched_off_before(mock_echo: Mock, mock_interactive: Mock) -> None:
    passed: dict[str, str | None] = {"TRUSTED_PROXY_ENABLED": None, "TRUSTED_ORIGINS": None}

    apply_https_settings(passed, {"TRUSTED_PROXY_ENABLED": "false"}, "https://ws.example.com")

    assert passed["TRUSTED_PROXY_ENABLED"] is None
    assert mock_echo.info.call_count == 0


@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.utils.public_url.echo")
def test_apply_https_settings_explicit_trusted_proxy_overrides_previous_off(
    mock_echo: Mock, mock_interactive: Mock
) -> None:
    passed: dict[str, str | None] = {"TRUSTED_PROXY_ENABLED": "true", "TRUSTED_ORIGINS": None}

    apply_https_settings(passed, {"TRUSTED_PROXY_ENABLED": "false"}, "https://ws.example.com")

    assert passed["TRUSTED_PROXY_ENABLED"] == "true"


@mock.patch("deepfellow.common.echo.Prompt.ask")
@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=True)
def test_apply_https_settings_enter_on_fresh_install_adds_no_origins(mock_interactive: Mock, mock_ask: Mock) -> None:
    mock_ask.return_value = None
    passed: dict[str, str | None] = {"TRUSTED_PROXY_ENABLED": None, "TRUSTED_ORIGINS": None}

    apply_https_settings(passed, {}, "https://ws.example.com")

    assert mock_ask.call_count == 1
    assert mock_ask.call_args.kwargs["default"] is None
    assert passed["TRUSTED_ORIGINS"] is None


@mock.patch("deepfellow.common.echo.Prompt.ask")
@mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=True)
def test_resolve_public_url_invalid_answer_is_asked_again(mock_interactive: Mock, mock_ask: Mock) -> None:
    mock_ask.side_effect = ["ws.example.com/app", "https://ws.example.com"]
    passed: dict[str, str | None] = {"PUBLIC_URL": None}

    result = resolve_public_url(passed, {}, 3000)

    assert mock_ask.call_count == 2
    assert result == "https://ws.example.com"
