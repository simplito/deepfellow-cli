# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
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
from deepfellow.common.validation import validate_server
from deepfellow.server.project.utils import archive_project
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def archive(
    ctx: typer.Context,
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Server address"),
    organization_id: str = typer.Argument(...),
    project_id: str = typer.Argument(...),
) -> None:
    """Archive a Project."""
    secrets_file = ctx.obj.get("cli-secrets-file")
    server = get_server_url(server)
    token = get_token(secrets_file, server, None)

    project = archive_project(server, token, organization_id, project_id)

    echo.info(str(project))
