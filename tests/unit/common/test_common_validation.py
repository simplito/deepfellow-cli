# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from collections.abc import Callable
from typing import Any
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.validation import (
    validate_bind_address,
    validate_connection_string,
    validate_df_name,
    validate_distinct_hours,
    validate_email,
    validate_hhmm,
    validate_mongo_url,
    validate_origin,
    validate_origins,
    validate_password,
    validate_port,
    validate_rabbitmq_credential,
    validate_redis_url,
    validate_server,
    validate_system,
    validate_truthy,
    validate_url,
    validate_username,
)


@mock.patch("deepfellow.common.validation.is_command_available")
def test_validate_system_passes_when_no_required_commands(mock_is_command_available: Mock) -> None:
    validate_system()

    assert mock_is_command_available.call_count == 0


@mock.patch("deepfellow.common.validation.echo")
@mock.patch("deepfellow.common.validation.is_command_available")
def test_validate_system_raises_when_command_missing(
    mock_is_command_available: Mock, mock_echo: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("deepfellow.common.validation.REQUIRED_COMMANDS", {"docker"})
    mock_is_command_available.return_value = False

    with pytest.raises(typer.Exit):
        validate_system()

    assert mock_is_command_available.call_count == 1
    assert mock_echo.error.call_count == 2


@mock.patch("deepfellow.common.validation.is_command_available")
def test_validate_system_passes_when_required_commands_available(
    mock_is_command_available: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("deepfellow.common.validation.REQUIRED_COMMANDS", {"docker"})
    mock_is_command_available.return_value = True

    validate_system()

    assert mock_is_command_available.call_count == 1
    assert mock_is_command_available.call_args == mock.call("docker")


@pytest.mark.parametrize(
    "email",
    [
        "admin@example.com",
        "admin@firma.local",
        "admin@host.internal",
        "admin@localhost",
        "First.Last+tag@example.com",
    ],
)
def test_validate_email_valid_returns_value_unchanged(email: str) -> None:
    result = validate_email(email)

    assert result == email


def test_validate_email_returns_value_with_lowercased_domain() -> None:
    result = validate_email("First.Last+tag@Example.COM")

    assert result == "First.Last+tag@example.com"


@pytest.mark.parametrize(
    "email",
    [
        "",
        "not-an-email",
        "user example.com",
        "a b@x.com",
        "user@exa mple.com",
        "a@b@c",
        "a!@x.com",
        "@example.com",
        "user@",
        "user@example..com",
        "user@.example.com",
        "a@b.com\n",
        "\na@b.com",
    ],
)
def test_validate_email_raises_when_invalid(email: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_email(email)


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com",
        "http://example.com/path?query=1",
        "https://sub.example.com:8080",
    ],
)
def test_validate_url_valid(value: str) -> None:
    result = validate_url(value)

    assert result == value


@pytest.mark.parametrize(
    "value",
    [
        "example.com",
        "not a url",
        "/just/a/path",
    ],
)
def test_validate_url_raises_when_missing_scheme_or_domain(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_url(value)


@mock.patch("deepfellow.common.validation.urlparse")
def test_validate_url_raises_when_urlparse_errors(mock_urlparse: Mock) -> None:
    mock_urlparse.side_effect = ValueError("boom")

    with pytest.raises(typer.BadParameter):
        validate_url("https://example.com")

    assert mock_urlparse.call_count == 1


@pytest.mark.parametrize(
    "value",
    [
        "localhost",
        "localhost:8080",
        "192.168.1.1:1",
        "example.com:65535",
    ],
)
def test_validate_connection_string_valid(value: str) -> None:
    result = validate_connection_string(value)

    assert result == value


def test_validate_connection_string_raises_when_too_many_parts() -> None:
    with pytest.raises(typer.BadParameter):
        validate_connection_string("host:8080:extra")


def test_validate_connection_string_raises_when_host_empty() -> None:
    with pytest.raises(typer.BadParameter):
        validate_connection_string(":8080")


def test_validate_connection_string_raises_when_port_not_a_number() -> None:
    with pytest.raises(typer.BadParameter):
        validate_connection_string("host:notaport")


@pytest.mark.parametrize(
    "value",
    [
        "host:0",
        "host:65536",
    ],
)
def test_validate_connection_string_raises_when_port_out_of_range(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_connection_string(value)


@pytest.mark.parametrize("value", ["1", "8080", 1, 65535])
def test_validate_port_valid(value: str | int) -> None:
    result = validate_port(value)

    assert result == int(value)


def test_validate_port_raises_when_not_a_number() -> None:
    with pytest.raises(typer.BadParameter):
        validate_port("notaport")


def test_validate_port_raises_when_none() -> None:
    with pytest.raises(typer.BadParameter):
        validate_port(None)


@pytest.mark.parametrize("value", ["0", "65536"])
def test_validate_port_raises_when_out_of_range(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_port(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", ""),
        ("127.0.0.1", "127.0.0.1"),
        ("0.0.0.0", "0.0.0.0"),
        ("::1", "[::1]"),
        ("[::1]", "[::1]"),
        ("::", "[::]"),
    ],
)
def test_validate_bind_address_returns_normalized_address(value: str | None, expected: str | None) -> None:
    result = validate_bind_address(value)

    assert result == expected


@pytest.mark.parametrize("value", ["localhost", "1.2.3.4:80", "256.0.0.1", "[127.0.0.1"])
def test_validate_bind_address_raises_when_not_an_ip_address(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_bind_address(value)


def test_validate_server_strips_trailing_slash() -> None:
    result = validate_server("https://example.com/")

    assert result == "https://example.com"


def test_validate_server_raises_when_url_invalid() -> None:
    with pytest.raises(typer.BadParameter):
        validate_server("not-a-url")


def test_validate_df_name_returns_value_when_valid() -> None:
    result = validate_df_name("my-df")

    assert result == "my-df"


def test_validate_df_name_raises_when_none() -> None:
    with pytest.raises(typer.BadParameter):
        validate_df_name(None)


def test_validate_df_name_raises_when_empty() -> None:
    with pytest.raises(typer.BadParameter):
        validate_df_name("")


def test_validate_df_name_raises_when_not_str() -> None:
    with pytest.raises(typer.BadParameter):
        validate_df_name(123)  # type: ignore[arg-type]


def test_validate_truthy_returns_value_when_truthy() -> None:
    result = validate_truthy("value")

    assert result == "value"


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        0,
        [],
    ],
)
def test_validate_truthy_raises_when_falsy(value: Any) -> None:
    with pytest.raises(typer.BadParameter):
        validate_truthy(value)


@pytest.mark.parametrize("value", ["00:00", "22:00", "23:59", "06:05"])
def test_validate_hhmm_returns_value_when_valid(value: str) -> None:
    assert validate_hhmm(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "bad",
        "25:00",
        "22:60",
        "9:00",
        "22:0",
        "22-00",
        "22:00:00",
    ],
)
def test_validate_hhmm_raises_when_malformed(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_hhmm(value)


@pytest.mark.parametrize(
    "value",
    [
        "abc",
        "abc123",
        "a_bc",
        "Username_1",
    ],
)
def test_validate_username_valid(value: str) -> None:
    result = validate_username(value)

    assert result == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "ab",
        "1abc",
        "abc!",
        "a" * 21,
        "username\n",
    ],
)
def test_validate_username_raises_when_invalid(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_username(value)


@pytest.mark.parametrize(
    "password",
    [
        "Abcde1@hij",  # minimal valid length with all required types
        "Abc123456!",  # alphanumeric with special char
        "aA1!@#$%^&*()-_=+",  # all allowed special chars with uppercase and digit
        "Password123_+=",
        "Abc123/xyz",  # '/' is a special character
        "Aa1!" + "a" * 124,  # 128 characters
        "Aa1!" + "a" * 500,  # no upper length limit
        "Pass word1?",  # any character counts as special, including space
    ],
)
def test_validate_password_valid(password: str) -> None:
    result = validate_password(password)

    assert result == password


@pytest.mark.parametrize(
    "password",
    [
        "",  # empty
        "short",  # too short
        "Abc1!xyz",  # too short
        "abcde1234!",  # no uppercase
        "ABCDE1234!",  # no lowercase
        "Abcdefghij",  # no digit
        "Abcde12345",  # no special char
        "Abcde12345!\n",  # trailing newline
    ],
)
def test_validate_password_raises_when_invalid(password: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_password(password)


def test_validate_distinct_hours_accepts_different_hours() -> None:
    validate_distinct_hours("22:00", "06:00")


def test_validate_distinct_hours_rejects_equal_hours() -> None:
    with pytest.raises(typer.BadParameter):
        validate_distinct_hours("22:00", "22:00")


@pytest.mark.parametrize("value", ["user", "p4ssw0rd", "Some_Long-Pass.word!"])
def test_validate_rabbitmq_credential_returns_value_when_safe(value: str) -> None:
    assert validate_rabbitmq_credential(value) == value


@pytest.mark.parametrize("value", ["", None, "a@b", "a/b", "a:b", "a?b", "a#b", "a[b", "a]b", "a%b", "a b"])
def test_validate_rabbitmq_credential_raises_when_empty_or_breaks_uri(value: str | None) -> None:
    with pytest.raises(typer.BadParameter):
        validate_rabbitmq_credential(value)


@pytest.mark.parametrize(
    "value",
    ["mongodb://localhost:27017", "mongodb://a:1,b:2/?replicaSet=rs0", "mongodb+srv://user:pw@cluster.example.com/db"],
)
def test_validate_mongo_url_accepts_mongo_urls(value: str) -> None:
    assert validate_mongo_url(value) == value


@pytest.mark.parametrize("value", ["", "localhost:27017", "http://localhost", "mongodb://", "redis://localhost"])
def test_validate_mongo_url_rejects_other_values(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_mongo_url(value)


@pytest.mark.parametrize("value", ["redis://localhost:6379", "rediss://user:pw@cache.example.com:6380"])
def test_validate_redis_url_accepts_redis_urls(value: str) -> None:
    assert validate_redis_url(value) == value


@pytest.mark.parametrize("value", ["", "localhost:6379", "http://localhost", "redis://", "mongodb://localhost"])
def test_validate_redis_url_rejects_other_values(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_redis_url(value)


@pytest.mark.parametrize(
    "validator",
    [
        validate_email,
        validate_url,
        validate_connection_string,
        validate_server,
        validate_username,
        validate_hhmm,
        validate_password,
        validate_mongo_url,
        validate_redis_url,
        validate_origin,
    ],
)
def test_validate_optional_value_none_returns_none(validator: Callable[[Any], Any]) -> None:
    assert validator(None) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://localhost", "http://localhost"),
        ("https://example.com", "https://example.com"),
        ("https://example.com:8443", "https://example.com:8443"),
        ("http://example.com/", "http://example.com"),
    ],
)
def test_validate_origin_accepts_origins(value: str, expected: str) -> None:
    assert validate_origin(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "example.com",
        "ftp://example.com",
        "http://",
        "https://user:pw@example.com",
        "https://example.com/path",
        "https://example.com?x=1",
        "https://example.com#frag",
        "https://example.com/;p",
    ],
)
def test_validate_origin_rejects_invalid_values(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_origin(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://a.example.com", "https://a.example.com"),
        ("https://a.example.com, https://b.example.com:8443", "https://a.example.com,https://b.example.com:8443"),
        (" https://a.example.com ,, http://localhost:3000 ,", "https://a.example.com,http://localhost:3000"),
        ("https://a.example.com/, https://b.example.com:8443/", "https://a.example.com,https://b.example.com:8443"),
    ],
)
def test_validate_origins_returns_normalized_list(value: str, expected: str) -> None:
    result = validate_origins(value)

    assert result == expected


@pytest.mark.parametrize("value", [None, "", " , ,"])
def test_validate_origins_empty_returns_none(value: str | None) -> None:
    result = validate_origins(value)

    assert result is None


def test_validate_origins_rejects_invalid_entry_by_name() -> None:
    with pytest.raises(typer.BadParameter) as exc_info:
        validate_origins("https://a.example.com,not-an-origin")

    assert "'not-an-origin'" in str(exc_info.value)
