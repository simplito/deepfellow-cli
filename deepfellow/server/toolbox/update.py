# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server toolbox update command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get_server_url
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.server.toolbox.utils import update_toolbox
from deepfellow.server.utils.login import get_token

app = typer.Typer()


@app.command()
def update(
    project_id: str = typer.Argument(...),
    toolbox_id: str = typer.Argument(...),
    name: str = typer.Option(..., help="New name for the Toolbox"),
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Server address"),
    organization_id: str | None = typer.Option(None, help="Organization ID, if your user belongs to more than one"),
) -> None:
    """Update an existing Toolbox."""
    secrets_file = state.cli_secrets_file
    server_url = get_server_url(server)
    token = get_token(secrets_file, server_url)

    toolbox = update_toolbox(server_url, token, project_id, organization_id, toolbox_id, name)

    echo.info(str(toolbox))
