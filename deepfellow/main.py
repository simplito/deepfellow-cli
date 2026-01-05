# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Main typer module."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version
from pathlib import Path

import typer

from deepfellow.common.config import EnvDict, env_to_dict, read_env_file
from deepfellow.common.defaults import DF_CLI_CONFIG_PATH, DF_CLI_SECRETS_PATH
from deepfellow.common.validation import validate_system

from .common.colors import COLORS, RESET
from .common.echo import echo
from .infra import app as infra_app
from .server import app as server_app

app = typer.Typer(invoke_without_command=True)


def print_name() -> None:
    """Print out the DeepFellow name in ASCII art."""
    print(f"""
┌─────────────────────────────────────────────────┐
│                                                 │
│   {COLORS.very_light_blue}▓▓▓▓▓   ▓▓▓▓▓  ▓▓▓▓▓  ▓▓▓▓▓{RESET}                   │
│   {COLORS.light_blue}▓▓  ▓▓  ▓▓     ▓▓     ▓▓  ▓▓{RESET}                  │
│   {COLORS.lighter_blue}▓▓  ▓▓  ▓▓▓▓   ▓▓▓▓   ▓▓▓▓▓{RESET}                   │
│   {COLORS.light_medium_blue}▓▓  ▓▓  ▓▓     ▓▓     ▓▓{RESET}                      │
│   {COLORS.medium_light_blue}▓▓▓▓▓   ▓▓▓▓▓  ▓▓▓▓▓  ▓▓{RESET}                      │
│                                                 │
│   {COLORS.medium_blue}▓▓▓▓▓  ▓▓▓▓▓  ▓▓     ▓▓     ▓▓▓▓▓▓  ▓▓   ▓▓{RESET}   │
│   {COLORS.blue}▓▓     ▓▓     ▓▓     ▓▓     ▓▓  ▓▓  ▓▓   ▓▓{RESET}   │
│   {COLORS.darker_blue}▓▓▓▓   ▓▓▓▓   ▓▓     ▓▓     ▓▓  ▓▓  ▓▓ ▓ ▓▓{RESET}   │
│   {COLORS.dark_blue}▓▓     ▓▓     ▓▓     ▓▓     ▓▓  ▓▓  ▓▓▓▓▓▓▓{RESET}   │
│   {COLORS.very_dark_blue}▓▓     ▓▓▓▓▓  ▓▓▓▓▓  ▓▓▓▓▓  ▓▓▓▓▓▓  ▓▓ ▓ ▓▓{RESET}   │
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
    secrets: Path = typer.Option(
        DF_CLI_SECRETS_PATH, envvar="DF_CLI_SECRETS_PATH", help="Path to the CLI secrets file."
    ),
    debug: bool = typer.Option(False, "-v", "-vv", "--verbose", "--debug", help="Display debug information"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Automatically answer to all questions"),
) -> None:
    """DeepFellow Command Line Interface."""
    if ctx.invoked_subcommand is None:
        print_name()
        raise typer.Exit(0)

    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["yes"] = yes
    ctx.obj["cli-secrets-file"] = secrets
    ctx.obj["cli-config-file"] = config
    echo.debug(f"{config=}")
    cli_config: EnvDict = {}
    if config.is_file():
        envs = read_env_file(config)
        cli_config = env_to_dict(envs)

    ctx.obj["cli-config"] = cli_config
    echo.debug(f"{cli_config=}")

    # Check environment if all commands are installed
    validate_system()


@app.command()
def version() -> None:
    """Print version info."""
    try:
        echo.success(get_version("deepfellow-cli"))
    except PackageNotFoundError:
        echo.error("No version information available. Have you installed the command?")


# Add object-based command groups
app.add_typer(infra_app, name="infra")
app.add_typer(server_app, name="server")

if __name__ == "__main__":
    app()
