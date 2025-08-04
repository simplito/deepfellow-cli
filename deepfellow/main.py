"""Main typer module."""

import json
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version
from pathlib import Path

import typer

from deepfellow.common.validation import validate_system

from .common.defaults import DF_CLI_CONFIG_PATH
from .common.echo import echo
from .infra import app as infra_app
from .server import app as server_app

app = typer.Typer(invoke_without_command=True)


def print_name() -> None:
    """Print out the DeepFellow name in ASCII art."""
    print("""
┌─────────────────────────────────────────────────┐
│                                                 │
│   \033[37m▓▓▓▓▓   ▓▓▓▓▓  ▓▓▓▓▓  ▓▓▓▓▓\033[0m                   │
│   \033[97m▓▓  ▓▓  ▓▓     ▓▓     ▓▓  ▓▓\033[0m                  │
│   \033[37m▓▓  ▓▓  ▓▓▓▓   ▓▓▓▓   ▓▓▓▓▓\033[0m                   │
│   \033[90m▓▓  ▓▓  ▓▓     ▓▓     ▓▓\033[0m                      │
│   \033[30m▓▓▓▓▓   ▓▓▓▓▓  ▓▓▓▓▓  ▓▓\033[0m                      │
│                                                 │
│   \033[37m▓▓▓▓▓  ▓▓▓▓▓  ▓▓     ▓▓     ▓▓▓▓▓▓  ▓▓   ▓▓\033[0m   │
│   \033[97m▓▓     ▓▓     ▓▓     ▓▓     ▓▓  ▓▓  ▓▓   ▓▓\033[0m   │
│   \033[37m▓▓▓▓   ▓▓▓▓   ▓▓     ▓▓     ▓▓  ▓▓  ▓▓ ▓ ▓▓\033[0m   │
│   \033[90m▓▓     ▓▓     ▓▓     ▓▓     ▓▓  ▓▓  ▓▓▓▓▓▓▓\033[0m   │
│   \033[30m▓▓     ▓▓▓▓▓  ▓▓▓▓▓  ▓▓▓▓▓  ▓▓▓▓▓▓  ▓▓ ▓ ▓▓\033[0m   │
│                                                 │
└─────────────────────────────────────────────────┘
`deepfellow --help` for help with commands.
""")


@app.callback()
def main(
    ctx: typer.Context,
    config: Path = typer.Option(
        DF_CLI_CONFIG_PATH, "--config", "-c", envvar="DF_CLI_CONFIG_PATH", help="Path to the CLI config file."
    ),
    debug: bool = typer.Option(False, "-v", "-vv", "--verbose", "--debug", help="Display debug information"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Automatically answer to all questions"),
) -> None:
    """Display callback function."""
    if ctx.invoked_subcommand is None:
        print_name()
        raise typer.Exit(0)

    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["yes"] = yes
    ctx.obj["cli-config"] = {}
    echo.debug(f"{config=}")
    if config.is_file():
        cli_config = json.loads(config.read_text(encoding="utf-8"))
        ctx.obj["cli-config"] = cli_config
        echo.debug(f"{cli_config=}")
        # TODO Store and reuse CLI config

    # Check environment if all commands are installed
    validate_system()


@app.command()
def version() -> None:
    """Print version info."""
    try:
        echo.success(get_version("deepfellow-cli"))
    except PackageNotFoundError:
        echo.error("No version information available. Have you installed the command?")


@app.command()
def log_check() -> None:
    """Log check - a temporary function."""
    echo.debug("Debug")
    echo.info("Info")
    echo.success("Success")
    echo.warning("Warning")
    echo.error("Error")


# Add object-based command groups
app.add_typer(infra_app, name="infra")
app.add_typer(server_app, name="server")

if __name__ == "__main__":
    app()
