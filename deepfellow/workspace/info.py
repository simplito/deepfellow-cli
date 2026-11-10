# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""workspace info command."""

from collections.abc import Mapping
from pathlib import Path

import typer
from rich.markup import escape

from deepfellow.common.defaults import WORKSPACE_MONGO_VOLUME
from deepfellow.common.echo import echo
from deepfellow.workspace.utils.docker import workspace_running, workspace_url
from deepfellow.workspace.utils.images import image_tag
from deepfellow.workspace.utils.install import IMAGE_KEY, read_installed_env
from deepfellow.workspace.utils.options import directory_option
from deepfellow.workspace.utils.validation import check_workspace_directory

app = typer.Typer()

_HIDDEN = "[dim]*****[/dim]"
_DEFAULT_SMTP_PORT = "587"


def _line(label: str, value: str) -> str:
    """Render one summary line; `value` is markup, so callers escape plain text."""
    return f"[cyan bold]{escape(label)}[/]: {value}"


def _plain(value: str | None) -> str:
    """Render a plain value, or `not set` when there is none."""
    return f"[yellow]{escape(value)}[/yellow]" if value else "[dim]not set[/dim]"


def _secret(value: str | None, show: bool) -> str:
    """Render a secret value, hidden unless `show`."""
    if not value:
        return "[dim]not set[/dim]"
    return _plain(value) if show else _HIDDEN


def _running(directory: Path) -> str:
    """Tell whether the Workspace container is running, or `unknown` when Docker cannot be asked."""
    running = workspace_running(directory)
    return "unknown" if running is None else "yes" if running else "no"


def _service(env: Mapping[str, str], url_key: str, local: str, secret: bool) -> str:
    """Describe Mongo or Redis: the stack's own one, or the external one with its (hidden) URL."""
    url = env.get(url_key)
    if not url:
        return f"[yellow]local[/yellow] {escape(local)}".rstrip()
    return f"[yellow]external[/yellow] {_secret(url, secret)}"


def _email(env: Mapping[str, str]) -> str:
    """Describe the e-mail settings without the SMTP password."""
    host = env.get("SMTP_HOST")
    if not host:
        return "[yellow]off[/yellow]"
    port = env.get("SMTP_PORT") or _DEFAULT_SMTP_PORT
    sender = env.get("EMAIL_FROM_ADDRESS") or "no sender address"
    return f"[yellow]on[/yellow] ({escape(host)}:{escape(port)}, from {escape(sender)})"


def _summary(directory: Path, env: Mapping[str, str], secret: bool) -> list[str]:
    """Build the summary lines; `APP_SECRET`, the Mongo password and keyfile, and passwords are never included."""
    image = env.get(IMAGE_KEY, "")
    tag = image_tag(image) if image else None
    return [
        "Information about DeepFellow Workspace:",
        _line("Version", _plain(tag.removeprefix("v") if tag else "unknown")),
        _line("Image", _plain(image)),
        _line("Directory", _plain(str(directory))),
        _line("Running", _plain(_running(directory))),
        _line("Public URL", _plain(env.get("PUBLIC_URL"))),
        _line("Local address", _plain(workspace_url(directory))),
        _line("DeepFellow Server URL", _plain(env.get("DF_SERVER_URL"))),
        _line("Organization id", _plain(env.get("DF_SERVER_ORGANIZATION_ID"))),
        _line("Project id", _plain(env.get("DF_SERVER_PROJECT_ID"))),
        _line("API key", _secret(env.get("DF_SERVER_API_KEY"), secret)),
        _line("Small model", _plain(env.get("SMALL_MODEL"))),
        _line("Mongo", _service(env, "MONGO_DB_URL", f"(Docker volume of '{WORKSPACE_MONGO_VOLUME}')", secret)),
        _line("Redis", _service(env, "REDIS_URL", "", secret)),
        _line("E-mail", _email(env)),
        _line("MCP token", _secret(env.get("MCP_AUTH_TOKEN"), secret)),
    ]


@app.command()
def info(
    directory: Path = directory_option(),
    secret: bool = typer.Option(False, "--secret", help="Display sensitive values."),
) -> None:
    """Display a summary of the DeepFellow Workspace installation."""
    check_workspace_directory(directory)
    env = read_installed_env(directory)

    echo.info("\n".join(_summary(directory, env, secret)))
    if env.get("BOOTSTRAP_ADMIN_PASSWORD"):
        echo.warning(
            f"The initial admin password is still in {directory / '.env'}; once you have logged in, remove all "
            "three BOOTSTRAP_ADMIN_* lines from it (the app needs them together)."
        )
