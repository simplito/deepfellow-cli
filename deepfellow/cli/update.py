# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Update cli typer command."""

import typer

from deepfellow.cli.utils.command_resolver import PACKAGE_NAME, resolve_cli_command
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.system import is_command_available, run

app = typer.Typer()


class UpdateError(Exception):
    """Raised when the CLI update command exits with a non-zero status."""


def _build_update_command() -> list[str] | None:
    """Build the update command based on the detected installer."""
    if is_command_available("uv"):
        uv_tools = run(["uv", "tool", "list"], capture_output=True)
        if uv_tools and PACKAGE_NAME in uv_tools:
            return ["uv", "tool", "upgrade", PACKAGE_NAME]

    if is_command_available("pipx"):
        pipx_list = run(["pipx", "list"], capture_output=True)
        if pipx_list and PACKAGE_NAME in pipx_list:
            return ["pipx", "upgrade", PACKAGE_NAME]

    return None


@app.command()
def update() -> None:
    """Update DeepFellow CLI."""
    cmd = resolve_cli_command("DF_UPDATE_COMMAND", _build_update_command)
    if cmd is None:
        echo.error("Unable to detect package manager. Update manually: pip install --upgrade deepfellow-cli")
        raise typer.Exit(1)

    echo.info("Updating DeepFellow CLI...")
    try:
        run(cmd, raises=UpdateError)
    except UpdateError as exc:
        echo.error("Failed to update DeepFellow CLI.")
        reraise_if_debug(exc)

    echo.success("DeepFellow CLI updated successfully.")
