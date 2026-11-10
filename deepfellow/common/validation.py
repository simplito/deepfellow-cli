# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Common validations."""

import ipaddress
import re
from typing import Any, cast
from urllib.parse import urlparse

import typer

from .echo import echo
from .system import is_command_available

# Empty as no system command is required for server login and organization or project commands
REQUIRED_COMMANDS: set[str] = set()
EMAIL_REGEX = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*"
USERNAME_REGEX = r"[a-zA-Z][a-zA-Z0-9_]{2,19}"
PASSWORD_REGEX = r"(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,}"
PASSWORD_REQUIREMENTS = (
    "Password must be at least 10 characters with at least 1 uppercase letter, 1 lowercase letter, 1 digit "
    "and 1 character other than A-Z, a-z, 0-9."
)


def validate_system() -> None:
    """Validate if the system has all dependencies."""
    failed_commands: list[str] = []
    # TODO Validate for Python version
    for command in REQUIRED_COMMANDS:
        if not is_command_available(command):
            failed_commands.append(command)

    if failed_commands:
        echo.error("System is not ready for DeepFellow.")
        echo.error("\n".join(f"Please install `{command}` command" for command in failed_commands))
        raise typer.Exit(1)


def validate_email(value: str | None) -> str | None:
    """Validate the email syntax (no DNS checks) and lowercase its domain, like `email_validator` did."""
    if value is None:
        # We allow email collected via option to be None
        return None

    if not re.fullmatch(EMAIL_REGEX, value):
        raise typer.BadParameter("Invalid email address")

    local_part, _, domain = value.rpartition("@")
    return f"{local_part}@{domain.lower()}"


def validate_url(value: str | None) -> str | None:
    """Validate the URL entry."""
    if value is None:
        return None

    try:
        result = urlparse(value)
    except Exception as exc:
        raise typer.BadParameter("Invalid URL") from exc

    if not all([result.scheme, result.netloc]):
        raise typer.BadParameter("Invalid URL - must include scheme and domain")

    return value


def _validate_url_scheme(value: str | None, schemes: tuple[str, ...], name: str) -> str | None:
    """Validate that the value is a URL with one of the given schemes and a host."""
    if value is None:
        return None

    result = urlparse(value)
    if result.scheme not in schemes or not result.netloc:
        raise typer.BadParameter(f"Invalid {name} URL - expected {' or '.join(f'{x}://' for x in schemes)}<host>...")

    return value


def validate_mongo_url(value: str | None) -> str | None:
    """Validate a MongoDB connection string (mongodb:// or mongodb+srv://)."""
    return _validate_url_scheme(value, ("mongodb", "mongodb+srv"), "MongoDB")


def validate_redis_url(value: str | None) -> str | None:
    """Validate a Redis URL (redis:// or rediss://)."""
    return _validate_url_scheme(value, ("redis", "rediss"), "Redis")


def validate_origin(value: str | None) -> str | None:
    """Validate a browser origin: http(s)://<host>[:port], without credentials, path, query or fragment.

    A trailing `/` is removed: browsers send the `Origin` header without it, and an app comparing origins as
    strings would never match a value that has one.

    Args:
        value: The origin, or `None`.

    Returns:
        The origin without a trailing `/`, or `None`.

    Raises:
        typer.BadParameter: When the value is not a valid origin.
    """
    if value is None:
        return None

    result = urlparse(value)
    if (
        result.scheme not in ("http", "https")
        or not result.hostname
        or result.username is not None
        or result.path not in ("", "/")
        or result.params
        or result.query
        or result.fragment
    ):
        raise typer.BadParameter("Invalid origin - expected http(s)://<host>[:port], no path, query or credentials")

    return value.rstrip("/")


def validate_origins(value: str | None) -> str | None:
    """Validate a comma-separated list of browser origins (see `validate_origin`).

    Whitespace around entries and empty entries are dropped, and each entry is normalized by `validate_origin`.

    Args:
        value: Comma-separated origins, or `None`.

    Returns:
        The entries joined with commas, or `None` when there are none.

    Raises:
        typer.BadParameter: When an entry is not a valid origin; the message names it.
    """
    if value is None:
        return None
    origins: list[str] = []
    for entry in value.split(","):
        if not (origin := entry.strip()):
            continue
        try:
            origins.append(validate_origin(origin) or origin)
        except typer.BadParameter:
            raise typer.BadParameter(
                f"Invalid origin {origin!r} - expected http(s)://<host>[:port], no path, query or credentials"
            ) from None
    return ",".join(origins) or None


def validate_connection_string(value: str | None) -> str | None:
    """Validate connection string in format: host[:port]."""
    if value is None:
        return None

    # Split host and port
    parts = value.split(":")

    if len(parts) > 2:
        raise typer.BadParameter("Invalid connection string - expected format: host[:port]")

    host = parts[0].strip()
    if not host:
        raise typer.BadParameter("Host cannot be empty")

    # Jeśli jest port, zwaliduj
    if len(parts) == 2:
        port_str = parts[1].strip()
        try:
            port = int(port_str)
        except ValueError as exc:
            raise typer.BadParameter("Invalid port - must be a number between 1 and 65535") from exc

        if not (1 <= port <= 65535):
            raise typer.BadParameter("Port must be between 1 and 65535")

    return value


def validate_port(value: str | int | None) -> int:
    """Validate value is a TCP port number between 1 and 65535."""
    try:
        port = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise typer.BadParameter("Invalid port - must be a number between 1 and 65535.") from exc

    if not (1 <= port <= 65535):
        raise typer.BadParameter("Invalid port - must be a number between 1 and 65535.")

    return port


def validate_server(value: str | None) -> str | None:
    """Validate the server entry. Strip the last slash."""
    if value is None:
        return None

    return cast("str", validate_url(value)).rstrip("/")


def validate_df_name(value: str | None) -> str | None:
    """Validate the value for DF_NAME env. It must be non-empty string."""
    if not value:
        raise typer.BadParameter("Invalid Name - cannot be empty")

    if not isinstance(value, str):
        raise typer.BadParameter("Invalid Name - must be str")

    return value


def validate_truthy(value: Any) -> Any:
    """Validate the value is not None."""
    if not value:
        raise typer.BadParameter("Value can't be empty.")

    return value


def validate_distinct_hours(start: str, stop: str) -> None:
    """Reject a shift window whose start and stop hours are equal (it would never be open)."""
    if start == stop:
        raise typer.BadParameter("Start and stop hours must differ.")


_RABBITMQ_CREDENTIAL_FORBIDDEN = re.compile(r"[\s@/:?#\[\]%]")


def validate_rabbitmq_credential(value: str | None) -> str:
    """Validate a RabbitMQ username/password: non-empty and safe to embed in an amqp:// URI."""
    if not value:
        raise typer.BadParameter("Value can't be empty.")

    if _RABBITMQ_CREDENTIAL_FORBIDDEN.search(value):
        raise typer.BadParameter(
            "Invalid value - can't contain whitespace or any of @ / : ? # [ ] % (they would break the amqp:// URI)."
        )

    return value


def validate_hhmm(value: str | None) -> str | None:
    """Validate value is an "HH:MM" 24-hour time (00-23:00-59)."""
    if value is None:
        return None

    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
        raise typer.BadParameter("Invalid time - must be HH:MM, 24-hour (e.g. 22:00).")

    return value


def validate_username(value: str | None) -> str | None:
    """Validate value is a sane username."""
    if value is None:
        return None

    validate_truthy(value)
    if not re.fullmatch(USERNAME_REGEX, value):
        raise typer.BadParameter(
            "Invalid username - 3-20 characters: letters, numbers, and '_' only, starting with a letter."
        )

    return value


def validate_password(value: str | None) -> str | None:
    """Validate value is a sane password."""
    if value is None:
        return None

    if not re.fullmatch(PASSWORD_REGEX, value):
        raise typer.BadParameter(f"Invalid password - {PASSWORD_REQUIREMENTS.removeprefix('Password ')}")

    return value


def validate_bind_address(value: str | None) -> str | None:
    """Validate a host bind address; IPv6 is returned in brackets, empty means all interfaces."""
    if value is None or value == "":
        return value
    unbracketed = value[1:-1] if value.startswith("[") and value.endswith("]") else value
    try:
        address = ipaddress.ip_address(unbracketed)
    except ValueError as exc:
        raise typer.BadParameter("Invalid bind address - must be an IPv4 or IPv6 address.") from exc
    return f"[{address}]" if address.version == 6 else str(address)
