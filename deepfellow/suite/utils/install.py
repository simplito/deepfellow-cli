# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install suite core logic."""

from collections.abc import Callable
from typing import Any

import typer

from deepfellow.common.defaults import (
    DF_INFRA_DIRECTORY,
    DF_SERVER_DIRECTORY,
    DF_SERVER_PORT,
)
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get
from deepfellow.common.exceptions import InstallError, translate_to_install_error
from deepfellow.common.install import resolve_admin_kwargs, validate_non_interactive_admin_values
from deepfellow.common.state import state
from deepfellow.common.validation import PASSWORD_REQUIREMENTS, validate_email, validate_password, validate_truthy
from deepfellow.infra.utils.install import install as infra_install
from deepfellow.server.utils.install import install as server_install
from deepfellow.server.utils.login import get_token_from_login
from deepfellow.server.utils.options import set_default_server_directory
from deepfellow.server.utils.workspace import Workspace, create_workspace

WORKSPACE_ORGANIZATION_NAME = "Workspace"
WORKSPACE_PROJECT_NAME = "Default"
WORKSPACE_API_KEY_NAME = "app"

TOTAL_STEPS = 4


def _run_step(step: int, name: str, func: Callable[[], Any]) -> Any:
    """Run a single suite-install step, reporting its name/position and translating failures.

    Args:
        step: 1-based step number, for progress reporting.
        name: Human-readable step name, used in progress and error messages.
        func: Zero-argument callable performing the step.

    Returns:
        Whatever `func` returns.

    Raises:
        typer.Exit: If the step fails, after printing "Step N/{TOTAL_STEPS} (<name>) failed: <reason>".
    """
    echo.info(f"Step {step}/{TOTAL_STEPS}: {name}...")
    try:
        return func()
    except InstallError as exc:
        echo.error(f"Step {step}/{TOTAL_STEPS} ({name}) failed: {exc}")
        raise typer.Exit(1) from exc
    except typer.Exit as exc:
        echo.error(f"Step {step}/{TOTAL_STEPS} ({name}) failed; see console output above for details.")
        raise typer.Exit(1) from exc


@translate_to_install_error
def install(
    admin_name: str | None = None,
    admin_email: str | None = None,
    admin_password: str | None = None,
) -> None:
    """Provision a complete DeepFellow workspace: Infra, Server, admin user, and a ready-to-use workspace.

    Runs, in order: infra install (via the built-in `workspace` template, which also starts infra
    and installs the ollama service plus chat/embedding/fast models), server install (via the
    built-in `workspace` template, which also starts server and creates the admin user), server
    login, and one call to the server's atomic workspace-creation endpoint. `suite install` itself
    exposes no `--template` option - it always uses each command's built-in `workspace` template.

    This is a one-shot command: it does not track progress and cannot resume after a partial failure.
    A failure partway through must be recovered manually, or by continuing with individual
    `infra`/`server` subcommands.

    Args:
        admin_name: Admin user's name. Prompted interactively if not given.
        admin_email: Admin user's email. Prompted interactively if not given.
        admin_password: Admin user's password. Prompted interactively if not given.

    Raises:
        InstallError: If any step fails, or if --non-interactive is set and an admin name, email,
            or password is missing.
    """
    # No action_kwargs source here (unlike server install's create_admin post-start action) - {} makes
    # the CLI flags the only source, which is what suite install has ever supported.
    effective = resolve_admin_kwargs({}, admin_name, admin_email, admin_password)
    validate_non_interactive_admin_values(effective, "suite install")
    server_url = f"http://localhost:{DF_SERVER_PORT}"

    # Resolved once, up front: create-admin and login must use the exact same credentials, so the
    # admin created during server install can actually log in during the login step (server install's
    # create_admin post-start action prompts internally but never returns what it prompted for).
    name = effective["name"] or echo.prompt_until_valid("Provide admin name", validate_truthy)
    email = effective["email"] or echo.prompt_until_valid("Provide admin email", validate_email)

    if not effective["password"]:
        echo.info(PASSWORD_REQUIREMENTS)
    password = effective["password"] or echo.prompt_until_valid(
        "Provide admin password", validate_password, password=True
    )

    _run_step(1, "infra install", lambda: infra_install(template="workspace"))
    _run_step(2, "server install", lambda: _server_install(name, email, password))

    token = _run_step(
        3,
        "server login",
        lambda: get_token_from_login(state.cli_secrets_file, server_url, email=email, password=password),
    )

    workspace: Workspace = _run_step(
        4,
        "workspace creation",
        lambda: create_workspace(
            server_url, token, WORKSPACE_ORGANIZATION_NAME, WORKSPACE_PROJECT_NAME, WORKSPACE_API_KEY_NAME
        ),
    )

    echo.success("DeepFellow workspace installed successfully.")
    echo.info(str(workspace))


def _server_install(name: str, email: str, password: str) -> None:
    infra_api_key = env_get(DF_INFRA_DIRECTORY / ".env", "DF_INFRA_API_KEY")
    if not infra_api_key:
        raise InstallError(
            f"DF_INFRA_API_KEY not found in {DF_INFRA_DIRECTORY / '.env'}; cannot configure Server-Infra auth."
        )

    server_install(
        template="workspace",
        infra_api_key=infra_api_key,
        admin_name=name,
        admin_email=email,
        admin_password=password,
    )
    set_default_server_directory(DF_SERVER_DIRECTORY, force=False)
