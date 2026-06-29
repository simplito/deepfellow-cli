# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Top-level prune command for a full DeepFellow teardown."""

from pathlib import Path

import typer

from deepfellow.cli.uninstall import _down_docker_compose, _get_uninstall_command
from deepfellow.common.defaults import DF_DEEPFELLOW_DIRECTORY, DF_INFRA_DIRECTORY
from deepfellow.common.echo import echo
from deepfellow.common.state import state
from deepfellow.common.system import rmtree, run
from deepfellow.server.utils.options import get_default_server_directory

app = typer.Typer()


def _prune_service(name: str, directory: Path) -> None:
    """Tear down one service: docker compose down -v then remove its directory.

    Tolerates a missing installation by skipping the step instead of aborting.

    Args:
        name: Human-readable service name, e.g. "Server" or "Infra".
        directory: Service installation directory to remove.
    """
    if not directory.exists():
        echo.info(f"DeepFellow {name} not installed, skipping.")
        return

    echo.info(f"Pruning DeepFellow {name}...")
    _down_docker_compose(directory)
    rmtree(directory)
    echo.success(f"DeepFellow {name} removed.")


@app.command()
def prune() -> None:
    """Remove everything: DeepFellow Server, Infra, the CLI, and ~/.deepfellow/.

    Resolves the uninstall command and configured server directory up front, before
    the steps that wipe the config holding them. Package removal runs last because it
    deletes the running script.
    """
    cmd = _get_uninstall_command()

    if not state.yes and not echo.confirm(
        "This will permanently remove all DeepFellow data and uninstall the CLI. Are you sure?"
    ):
        raise typer.Exit(0)

    server_directory = get_default_server_directory()

    _prune_service("Server", server_directory)
    _prune_service("Infra", DF_INFRA_DIRECTORY)

    if DF_DEEPFELLOW_DIRECTORY.exists():
        echo.info("Removing remaining DeepFellow files...")
        rmtree(DF_DEEPFELLOW_DIRECTORY)
        echo.success("DeepFellow files removed.")

    if not cmd:
        echo.warning("Unable to detect package manager. Uninstall manually: pip uninstall deepfellow-cli")
        return

    echo.info("Uninstalling DeepFellow CLI...")
    run(cmd)
    echo.success("DeepFellow CLI uninstalled.")
