# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared install utilities used by infra, server, and suite install."""

import getpass
from pathlib import Path
from typing import Any

import typer

from deepfellow.common.docker import (
    is_docker_group_available,
    is_docker_installed,
    is_user_allowed_to_use_docker,
    is_user_in_docker_group,
)
from deepfellow.common.echo import echo, is_interactive
from deepfellow.common.exceptions import InstallError, reraise_if_debug


def ensure_directory(
    directory: Path,
    warning_message: str | None = None,
    confirm_message: str | None = None,
    error_message: str | None = None,
    force_install: bool | None = None,
    overwrite: bool | None = None,
) -> None:
    """Check if overriding the existing installation and create directory if needed.

    Args:
        directory: Directory to create/reuse.
        warning_message: Message shown when the directory already exists.
        confirm_message: Confirm prompt shown when `overwrite` is not pre-resolved.
        error_message: Message shown if directory creation fails.
        force_install: Skips the overwrite check entirely when set.
        overwrite: Pre-answered overwrite decision. `True` proceeds without prompting; `False`
            raises `typer.Exit(1)` without prompting; `None` (default) preserves the existing
            prompt behavior, including its non-interactive-mode messaging and fallback.
    """
    confirm_message = confirm_message or "Should I override existing installation?"
    error_message = error_message or f"Unable to create directory {directory}."
    warning_message = warning_message or f"Directory {directory} already exists."

    if directory.is_dir() and not force_install:
        if overwrite is None:
            echo.warning(warning_message)
            if not is_interactive():
                echo.info(
                    "Non-interactive mode is ON. To force a reinstall over the existing installation, pass "
                    f"--force-install, or remove the directory manually: rm -rf {directory}"
                )
            if not echo.confirm(confirm_message):
                raise typer.Exit(1)
        elif not overwrite:
            raise typer.Exit(1)

    try:
        directory.mkdir(parents=True, exist_ok=True)
    except Exception as exc_info:
        echo.error(error_message)
        reraise_if_debug(exc_info)


def assert_docker() -> None:
    """Raise typer.Exit(1) if docker is not installed, otherwise pass."""
    if not is_docker_installed():
        echo.error("Missing docker. Install docker.")
        raise typer.Exit(1)

    if not is_user_allowed_to_use_docker():
        echo.error("Unable to run docker command.")
        if not is_user_in_docker_group() and is_docker_group_available():
            username = getpass.getuser()
            echo.info(f"Add user to the docker group. `usermod -aG docker {username}`")
            raise typer.Exit(1)

        echo.info("Try running with sudo command.")
        raise typer.Exit(1)


def resolve_admin_kwargs(
    action_kwargs: dict[str, Any],
    admin_name: str | None,
    admin_email: str | None,
    admin_password: str | None,
) -> dict[str, str | None]:
    """Merge --admin-name/--admin-email/--admin-password over another source's own kwargs."""
    return {
        "name": admin_name if admin_name else action_kwargs.get("name"),
        "email": admin_email if admin_email else action_kwargs.get("email"),
        "password": admin_password if admin_password else action_kwargs.get("password"),
    }


def validate_non_interactive_admin_values(effective: dict[str, str | None], context: str) -> None:
    """Fail fast if --non-interactive can't fall back to a prompt for a missing admin value.

    Args:
        effective: The resolved {"name": ..., "email": ..., "password": ...} to check, as
            returned by resolve_admin_kwargs().
        context: Human-readable subject for the error message, e.g. "suite install" or
            "Template's 'server.create_admin' post-start action".

    Raises:
        InstallError: If --non-interactive is set and any of name/email/password is missing.
    """
    if is_interactive():
        return

    missing = [key for key in ("name", "email", "password") if not effective.get(key)]
    if missing:
        raise InstallError(
            f"{context} is missing {', '.join(missing)}; --non-interactive has no prompt to fall "
            "back on. Pass --admin-name/--admin-email/--admin-password"
        )
