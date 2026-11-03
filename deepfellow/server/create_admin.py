# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Create admin command."""

from pathlib import Path

import typer

from deepfellow.common import rest
from deepfellow.common.echo import echo
from deepfellow.common.state import state
from deepfellow.common.validation import validate_email
from deepfellow.server.utils.login import get_token_from_login
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.users import apply_admin, resolve_admin_creds
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


@app.command()
def create_admin(
    directory: Path = directory_option("Target directory for the DeepFellow Server installation."),
    name: str | None = typer.Argument(None, help="Admin name"),
    email: str | None = typer.Argument(None, callback=validate_email, help="Admin email"),
    password: str | None = typer.Option(None, help="Admin password"),
) -> None:
    """Create admin.

    Raises:
        typer.Exit: If an admin already exists for the given email - apply_admin() treats
            that as a no-op (needed for suite install --resume and a `--template` reinstall to
            safely re-enter this step), but this direct, explicit command has no such resume
            context: a user invoking it is asking to create an admin right now, so an existing
            account for that email is this command's own failure to report, not a success.
    """
    check_server_directory(directory)
    name, email, password = resolve_admin_creds(name, email, password)
    created = apply_admin(directory, name, email, password, silent_if_exists=True)
    if not created:
        echo.error("Unable to create an admin: an account with that email already exists.")
        raise typer.Exit(1)

    # Scripts (--non-interactive) opt in to the login with --yes; it writes tokens, so it is not a silent default.
    if echo.confirm("Do you want to log in as the new admin now?", default=not state.non_interactive):
        try:
            server = rest.get_server_url(None)
            echo.info(f"Logging in to {server}")
            get_token_from_login(state.cli_secrets_file, server, email=email, password=password)
        except typer.Exit:
            # The admin exists by now; a failed login must not turn that into a failed command.
            echo.warning("The admin was created, but logging in failed. Log in later with `deepfellow server login`.")
        else:
            echo.success("Logged in.")
