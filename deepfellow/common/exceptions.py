"""Common exceptions."""

import click
import typer


class ConfigValidationError(Exception):
    """Raised when config validation is failing."""


class GitError(Exception):
    """Raised when Git command failes."""


def reraise_if_debug(exc_info: Exception) -> None:
    """Reraise the exception if debug in Context."""
    ctx = click.get_current_context()
    if ctx.obj.get("debug", False):
        raise

    raise typer.Exit(1) from exc_info
