# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""server project list command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.server.project.utils import list_projects
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def list(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Server address"),
    organization_id: str = typer.Argument(...),
) -> None:
    """Display list of Projects."""
    # Get token for the server
    secrets_file = state.cli_secrets_file
    server_url = get_server_url(server)
    token = get_token(secrets_file, server_url)

    projects = list_projects(server_url, token, organization_id)
    echo.info("\n\n".join([str(org) for org in projects]))
