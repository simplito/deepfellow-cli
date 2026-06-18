# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Uninstall cli typer command."""

import shlex
from pathlib import Path

import typer

from deepfellow.common.config import read_env_file
from deepfellow.common.defaults import DF_DEEPFELLOW_DIRECTORY, DF_INFRA_DIRECTORY, DF_SERVER_DIRECTORY
from deepfellow.common.echo import echo
from deepfellow.common.state import state
from deepfellow.common.system import is_command_available, rmtree, run

app = typer.Typer()

_PACKAGE_NAME = "deepfellow-cli"


def _build_uninstall_command() -> list[str] | None:
    """Build the uninstall command based on the detected installer."""
    if is_command_available("uv"):
        uv_tools = run(["uv", "tool", "list"], capture_output=True)
        if uv_tools and _PACKAGE_NAME in uv_tools:
            return ["uv", "tool", "uninstall", _PACKAGE_NAME]

    if is_command_available("pipx"):
        pipx_list = run(["pipx", "list"], capture_output=True)
        if pipx_list and _PACKAGE_NAME in pipx_list:
            return ["pipx", "uninstall", _PACKAGE_NAME]

    if is_command_available("pip3"):
        return ["pip3", "uninstall", _PACKAGE_NAME, "-y"]

    if is_command_available("pip"):
        return ["pip", "uninstall", _PACKAGE_NAME, "-y"]

    return None


def _get_uninstall_command() -> list[str] | None:
    """Get the uninstall command from config or fall back to auto-detection."""
    if state.cli_config_file.is_file():
        try:
            envs = read_env_file(state.cli_config_file)
            cmd_str = envs.get("DF_UNINSTALL_COMMAND", "").strip()
            if cmd_str:
                try:
                    return shlex.split(cmd_str)
                except ValueError:
                    echo.warning("Invalid DF_UNINSTALL_COMMAND in config, falling back to auto-detection.")
        except FileNotFoundError:
            pass
    return _build_uninstall_command()


def _down_docker_compose(directory: Path) -> None:
    """Run docker compose down -v in the given directory, skipping if Docker is unavailable."""
    if not is_command_available("docker"):
        echo.warning("Docker not available, skipping container cleanup.")
        return

    try:
        run(["docker", "compose", "down", "-v"], directory, quiet=True)
    except typer.Exit:
        echo.warning(f"Failed to remove containers in {directory.as_posix()}. They may still be running.")


def _resolve_prune(prune: bool, yes: bool) -> bool:
    """Determine whether pruning should proceed, prompting the user if needed.

    Returns True when the caller should prune data, False otherwise.
    Raises typer.Exit(0) when the user declines the safety confirmation.
    """
    do_prune = prune
    if not do_prune and not yes:
        do_prune = echo.confirm("Also remove all DeepFellow data (infra and server containers, volumes, and files)?")
    if do_prune and not yes and not echo.confirm("All DeepFellow data will be permanently deleted. Are you sure?"):
        raise typer.Exit(0)
    return do_prune


@app.command()
def uninstall(
    prune: bool = typer.Option(
        False,
        "--prune",
        help="Also remove all DeepFellow data (infra and server containers, volumes, and files).",
    ),
) -> None:
    """Uninstall DeepFellow CLI."""
    cmd = _get_uninstall_command()
    if not cmd:
        echo.error("Unable to detect package manager. Uninstall manually: pip uninstall deepfellow-cli")
        raise typer.Exit(1)

    yes = state.yes
    do_prune = _resolve_prune(prune, yes)

    if not yes and not echo.confirm("This will uninstall the DeepFellow CLI. Are you sure?"):
        raise typer.Exit(0)

    if do_prune:
        if DF_INFRA_DIRECTORY.exists():
            echo.info("Pruning DeepFellow Infra...")
            _down_docker_compose(DF_INFRA_DIRECTORY)
            echo.success("DeepFellow Infra containers removed.")

        if DF_SERVER_DIRECTORY.exists():
            echo.info("Pruning DeepFellow Server...")
            _down_docker_compose(DF_SERVER_DIRECTORY)
            echo.success("DeepFellow Server containers removed.")

        if DF_DEEPFELLOW_DIRECTORY.exists():
            echo.info("Removing DeepFellow files...")
            rmtree(DF_DEEPFELLOW_DIRECTORY)
            echo.success("DeepFellow files removed.")

    echo.info("Uninstalling DeepFellow CLI...")
    run(cmd)
    echo.success("DeepFellow CLI uninstalled.")
