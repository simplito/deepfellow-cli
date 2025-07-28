"""Main typer module."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version

import typer

from .common.echo import echo
from .infra import app as infra_app
from .server import app as server_app

app = typer.Typer(invoke_without_command=True)


@app.callback()
def main(ctx: typer.Context, version: bool = typer.Option(False), debug: bool = typer.Option(False)) -> None:
    """Display callback function."""
    if version:
        try:
            echo.success(get_version("deepfellow-cli"))
        except PackageNotFoundError:
            echo.error("No version information available. Have you installed the command?")

    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug

    if ctx.invoked_subcommand is None:
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


@app.command()
def log_check(ctx: typer.Context) -> None:
    """Log check - a temporary function."""
    echo.debug("Debug", ctx)
    echo.info("Info", ctx)
    echo.success("Success", ctx)
    echo.warning("Warning", ctx)
    echo.error("Error", ctx)


# Add object-based command groups
app.add_typer(infra_app, name="infra")
app.add_typer(server_app, name="server")

if __name__ == "__main__":
    app()
