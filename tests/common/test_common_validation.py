# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from types import SimpleNamespace
from typing import Any
from unittest import mock
from unittest.mock import Mock

import pytest
import typer
from email_validator import EmailNotValidError

from deepfellow.common.validation import (
    validate_connection_string,
    validate_df_name,
    validate_email,
    validate_password,
    validate_port,
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


def test_validate_email_none_returns_none() -> None:
    assert validate_email(None) is None


@mock.patch("deepfellow.common.validation.validate_email_lib")
def test_validate_email_returns_normalized_email_when_valid(mock_validate_email_lib: Mock) -> None:
    mock_validate_email_lib.return_value = SimpleNamespace(email="user@example.com")

    result = validate_email("USER@EXAMPLE.COM")

    assert result == "user@example.com"
    assert mock_validate_email_lib.call_count == 1
    assert mock_validate_email_lib.call_args == mock.call("USER@EXAMPLE.COM")


@mock.patch("deepfellow.common.validation.validate_email_lib")
def test_validate_email_raises_when_invalid(mock_validate_email_lib: Mock) -> None:
    mock_validate_email_lib.side_effect = EmailNotValidError("bad email")

    with pytest.raises(typer.BadParameter):
        validate_email("not-an-email")


def test_validate_url_none_returns_none() -> None:
    assert validate_url(None) is None


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


def test_validate_connection_string_none_returns_none() -> None:
    assert validate_connection_string(None) is None


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


def test_validate_server_none_returns_none() -> None:
    assert validate_server(None) is None


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


def test_validate_username_none_returns_none() -> None:
    assert validate_username(None) is None


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
    ],
)
def test_validate_username_raises_when_invalid(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_username(value)


def test_validate_password_none_returns_none() -> None:
    assert validate_password(None) is None


@pytest.mark.parametrize(
    "password",
    [
        "Abcde1@hij",  # minimal valid length with all required types
        "Abc123456!",  # alphanumeric with special char
        "aA1!@#$%^&*()-_=+",  # all allowed special chars with uppercase and digit
        "Password123_+=",
        "Aa1!" + "a" * 124,  # exactly 128 characters
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
        "no$pecials?",  # contains '?'
        "Aa1!" + "a" * 125,  # too long (129 characters)
        "abcde1234!",  # no uppercase
        "ABCDE1234!",  # no lowercase
        "Abcdefghij",  # no digit
        "Abcde12345",  # no special char
    ],
)
def test_validate_password_raises_when_invalid(password: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_password(password)
