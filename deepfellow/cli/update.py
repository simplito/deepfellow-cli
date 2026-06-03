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

from deepfellow.common.echo import echo
from deepfellow.common.system import is_command_available, run

app = typer.Typer()

_PACKAGE_NAME = "deepfellow-cli"


def _build_update_command() -> list[str] | None:
    """Build the update command based on the detected installer."""
    if is_command_available("uv"):
        uv_tools = run(["uv", "tool", "list"], capture_output=True)
        if uv_tools and _PACKAGE_NAME in uv_tools:
            return ["uv", "tool", "upgrade", _PACKAGE_NAME]

    if is_command_available("pipx"):
        pipx_list = run(["pipx", "list"], capture_output=True)
        if pipx_list and _PACKAGE_NAME in pipx_list:
            return ["pipx", "upgrade", _PACKAGE_NAME]

    return None


@app.command()
def update() -> None:
    """Update DeepFellow CLI."""
    cmd = _build_update_command()
    if cmd is None:
        echo.error("Unable to detect package manager. Update manually: pip install --upgrade deepfellow-cli")
        raise typer.Exit(1)

    echo.info("Updating DeepFellow CLI...")
    if run(cmd) is None:
        raise typer.Exit(1)

    echo.success("DeepFellow CLI updated successfully.")
