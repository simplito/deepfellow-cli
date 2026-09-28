# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""infra mcp uninstall command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.mcp import uninstall as uninstall_util

app = typer.Typer()


@app.command()
def uninstall(
    name: str = typer.Argument(..., help="Name of the MCP server to uninstall."),
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
    purge: bool = typer.Option(False, help="Remove MCP server with all its files."),
) -> None:
    """Uninstall (stop) an MCP server instance - built-in or custom.

    Use `mcp remove` instead to delete a custom server's registration from the models list.
    """
    uninstall_util(name=name, server=server, purge=purge)

    echo.success(f"MCP server '{name}' uninstalled.")
