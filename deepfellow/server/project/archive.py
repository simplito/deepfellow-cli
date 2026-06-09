# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server project archive command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.server.project.utils import archive_project
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def archive(
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Server address"),
    organization_id: str = typer.Argument(...),
    project_id: str = typer.Argument(...),
) -> None:
    """Archive a Project."""
    yes = state.yes
    if yes:
        echo.debug("Automatically confirming the archive.")

    secrets_file = state.cli_secrets_file
    server_url = get_server_url(server)
    token = get_token(secrets_file, server_url)

    if not yes and not echo.confirm(
        "Are you sure you want to archive this project? This action cannot be undone.", default=False
    ):
        raise typer.Exit(1)

    project = archive_project(server_url, token, organization_id, project_id)

    echo.info(str(project))
