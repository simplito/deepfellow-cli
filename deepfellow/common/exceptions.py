"""Common exceptions."""

import click
import typer


class ConfigValidationError(Exception):
    """Raised when config validation is failing."""


class GitError(Exception):
    """Raised when Git command failes."""


class DockerSocketNotFoundError(Exception):
    """Raised if docker.sock file not found."""


class DockerNetworkError(Exception):
    """Raised if getting a list of networks fails."""


def reraise_if_debug(exc_info: Exception) -> None:
    """Reraise the exception if debug in Context."""
    ctx = click.get_current_context()
    if ctx.obj.get("debug", False):
        raise

    raise typer.Exit(1) from exc_info
