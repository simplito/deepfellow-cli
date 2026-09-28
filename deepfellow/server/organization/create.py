# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""server organization create command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.server.organization.utils import create_organization
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def create(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Server address"),
    name: str = typer.Argument(...),
) -> None:
    """Create organization."""
    # Get token for the server
    secrets_file = state.cli_secrets_file
    server_url = get_server_url(server)
    token = get_token(secrets_file, server_url)

    organization = create_organization(server_url, token, name)

    echo.info(str(organization))
