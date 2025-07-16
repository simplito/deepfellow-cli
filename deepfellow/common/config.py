"""Config for CLI."""

from pathlib import Path

import typer


def get_config(ctx: typer.Context) -> Path | None:
    """Get config from context."""
    if ctx.obj and ctx.obj.get("config"):
        return ctx.obj["config"]

    return None
