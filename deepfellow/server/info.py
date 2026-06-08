# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server info command."""

from pathlib import Path

import typer

from deepfellow.server.env_command.info import show_server_env_info
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def info(
    directory: Path = directory_option(),
    secret: bool = typer.Option(
        False,
        "--secret",
        help="Display sensitive values.",
    ),
    doc: bool = typer.Option(
        False,
        "--doc",
        help="Display environment variables documentation.",
    ),
) -> None:
    """Display runtime configuration values."""
    show_server_env_info(directory, secret=secret, doc=doc, show_prefix=False)
