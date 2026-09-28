# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""infra mcp list command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.mcp import list_servers

app = typer.Typer()


@app.command()
def list(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
) -> None:
    """Display list of MCP servers."""
    servers = list_servers(server=server)
    if not servers:
        echo.info("No MCP servers provisioned.")
        return

    echo.info("\n\n".join(str(mcp_server) for mcp_server in servers))
