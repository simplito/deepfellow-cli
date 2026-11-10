# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Validation for workspace commands."""

from pathlib import Path

import typer

from deepfellow.common.defaults import DOCKER_COMPOSE_CONFIG_FILENAME
from deepfellow.common.echo import echo
from deepfellow.common.system import check_service_directory
from deepfellow.common.validation import validate_port

MCP_AUTH_TOKEN_MIN_LENGTH = 16


def check_workspace_directory(directory: Path) -> None:
    """Exit when `directory` does not hold a DeepFellow Workspace installation.

    Args:
        directory: Workspace install directory.

    Raises:
        typer.Exit: When the directory or its compose file is missing.
    """
    message = f"No DeepFellow Workspace installation found in {directory}. Run 'workspace install' first."
    check_service_directory(directory, "Workspace", message)
    if not (directory / DOCKER_COMPOSE_CONFIG_FILENAME).is_file():
        echo.error(message)
        raise typer.Exit(1)


def validate_mcp_auth_token(value: str | None) -> str | None:
    """Validate the MCP bearer token length the app requires.

    Args:
        value: The token, or `None` when not given.

    Returns:
        The token without surrounding whitespace, or `None`.

    Raises:
        typer.BadParameter: When the token is shorter than the app accepts.
    """
    if value is None:
        return None
    value = value.strip()
    if len(value) < MCP_AUTH_TOKEN_MIN_LENGTH:
        raise typer.BadParameter(f"Token must be at least {MCP_AUTH_TOKEN_MIN_LENGTH} characters.")
    return value


def validate_port_text(value: str) -> str:
    """Validate a port kept in .env and return it as text.

    Args:
        value: The port.

    Returns:
        The port as text.

    Raises:
        typer.BadParameter: When the value is not a port between 1 and 65535.
    """
    return str(validate_port(value))


def validate_flag(value: str) -> str:
    """Validate a boolean setting the app reads as `true` or `false`.

    Args:
        value: The value, in any letter case.

    Returns:
        The value in lower case.

    Raises:
        typer.BadParameter: When the value is neither `true` nor `false`.
    """
    if value.lower() not in ("true", "false"):
        raise typer.BadParameter("Expected true or false.")
    return value.lower()
