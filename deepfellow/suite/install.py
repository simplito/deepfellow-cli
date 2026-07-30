# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install suite typer command."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import InstallError, reraise_if_debug
from deepfellow.common.validation import validate_email, validate_password
from deepfellow.suite.utils.install import install as install_util

app = typer.Typer()


@app.command()
def install(
    admin_name: str | None = typer.Option(None, "--admin-name", help="Admin user's name."),
    admin_email: str | None = typer.Option(None, "--admin-email", callback=validate_email, help="Admin user's email."),
    admin_password: str | None = typer.Option(
        None, "--admin-password", callback=validate_password, help="Admin user's password."
    ),
) -> None:
    """Provision a complete DeepFellow workspace: Infra, Server, admin user, and a ready-to-use workspace.

    Runs, in one non-interactive-friendly pass: infra install, infra start, infra service install
    (ollama, GPU spec), three infra model installs (chat, embedding, fast), server install (milvus,
    mxbai-embed-large), server start, create-admin, login, and one call to the server's atomic
    workspace-creation endpoint (organization "Workspace", project "Default", API key "app").

    All defaults are hardcoded in this version — there is no `--template` flag. This is a one-shot
    command: it does not track progress and cannot resume after a partial failure.
    """
    try:
        install_util(admin_name=admin_name, admin_email=admin_email, admin_password=admin_password)
    except InstallError as exc:
        echo.error(str(exc))
        reraise_if_debug(exc)
