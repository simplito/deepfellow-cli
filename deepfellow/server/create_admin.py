# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Create admin command."""

from pathlib import Path

import typer

from deepfellow.common.validation import validate_email
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.users import create_admin as create_admin_util
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


@app.command()
def create_admin(
    directory: Path = directory_option("Target directory for the DeepFellow Server installation."),
    name: str | None = typer.Argument(None, help="Admin name"),
    email: str | None = typer.Argument(None, callback=validate_email, help="Admin email"),
    password: str | None = typer.Option(None, help="Admin password"),
) -> None:
    """Create admin."""
    check_server_directory(directory)
    create_admin_util(directory, name, email, password)
