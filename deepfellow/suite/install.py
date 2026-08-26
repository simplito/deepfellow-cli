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
    admin_name: str | None = typer.Option(
        None, "--admin-name", envvar="DF_SERVER_ADMIN_NAME", help="Admin user's name."
    ),
    admin_email: str | None = typer.Option(
        None,
        "--admin-email",
        envvar="DF_SERVER_ADMIN_EMAIL",
        callback=validate_email,
        help="Admin user's email.",
    ),
    admin_password: str | None = typer.Option(
        None,
        "--admin-password",
        envvar="DF_SERVER_ADMIN_PASSWORD",
        callback=validate_password,
        help="Admin user's password.",
    ),
    force_install: bool = typer.Option(
        False,
        help="Force a reinstall over an already-existing infra/server directories.",
    ),
) -> None:
    """Provision a complete DeepFellow workspace: Infra, Server, admin user, and a ready-to-use workspace.

    Runs, in one non-interactive-friendly pass: infra install (via the built-in `workspace`
    template, which also starts infra and installs the ollama service plus chat/embedding/fast
    models), server install (via the built-in `workspace` template, which also starts server and
    creates the admin user), login, one call to the server's atomic workspace-creation endpoint
    (organization "Workspace", project "Default", API key "app"), and a follow-up call granting the
    created project access to the three models just installed.

    `suite install` itself exposes no `--template` option — it always uses each command's built-in
    `workspace` template. This is a one-shot command: it does not track progress and cannot resume
    after a partial failure.
    """
    try:
        install_util(
            admin_name=admin_name, admin_email=admin_email, admin_password=admin_password, force_install=force_install
        )
    except InstallError as exc:
        echo.error(str(exc))
        reraise_if_debug(exc)
