# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""infra mcp remove command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.mcp import remove as remove_util

app = typer.Typer()


@app.command()
def remove(
    name: str = typer.Argument(..., help="Name of the custom MCP server to remove."),
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
) -> None:
    """Remove a custom MCP server's registration from the models list.

    Only valid for a custom server registered via `mcp add` - a built-in model cannot be removed
    this way. Use `mcp uninstall` to stop a running instance without deleting its registration.
    """
    remove_util(name=name, server=server)

    echo.success(f"MCP server '{name}' removed.")
