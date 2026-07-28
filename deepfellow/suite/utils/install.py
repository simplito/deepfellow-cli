# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install suite core logic."""

import json
from collections.abc import Callable
from typing import Any

import typer

from deepfellow.common.defaults import (
    DF_INFRA_DIRECTORY,
    DF_INFRA_PORT,
    DF_SERVER_DIRECTORY,
    DF_SERVER_PORT,
    VectorDBTypeChoice,
)
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get
from deepfellow.common.exceptions import InstallError, translate_to_install_error
from deepfellow.common.state import state
from deepfellow.common.validation import PASSWORD_REQUIREMENTS, validate_email, validate_password, validate_truthy
from deepfellow.infra.utils.docker import start_infra
from deepfellow.infra.utils.install import install as infra_install
from deepfellow.infra.utils.model_install import install as infra_model_install
from deepfellow.infra.utils.service_install import install as infra_service_install
from deepfellow.infra.utils.validation import check_infra_directory
from deepfellow.server.utils.docker import start_server
from deepfellow.server.utils.install import install as server_install
from deepfellow.server.utils.login import get_token_from_login
from deepfellow.server.utils.options import set_default_server_directory
from deepfellow.server.utils.users import create_admin
from deepfellow.server.utils.validation import check_server_directory
from deepfellow.server.utils.workspace import Workspace, create_workspace

OLLAMA_SERVICE_SPEC = {
    "hardware": "GPU",
    "keep_alive": "-1",
    "is_flash_attention": True,
    "context_length": 250000,
}
CHAT_MODEL = "gemma4:e4b"
EMBEDDING_MODEL = "mxbai-embed-large"
FAST_MODEL = "qwen3.5:4b"
EMBEDDING_SIZE = 1024

WORKSPACE_ORGANIZATION_NAME = "Workspace"
WORKSPACE_PROJECT_NAME = "Default"
WORKSPACE_API_KEY_NAME = "app"

TOTAL_STEPS = 11


def _run_step(step: int, name: str, func: Callable[[], Any]) -> Any:
    """Run a single suite-install step, reporting its name/position and translating failures.

    Args:
        step: 1-based step number, for progress reporting.
        name: Human-readable step name, used in progress and error messages.
        func: Zero-argument callable performing the step.

    Returns:
        Whatever `func` returns.

    Raises:
        typer.Exit: If the step fails, after printing "Step N/11 (<name>) failed: <reason>".
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

    Runs, in order: infra install, infra start, infra service install (ollama), three infra model
    installs, server install, server start, server create-admin, server login, and one call to the
    server's atomic workspace-creation endpoint. All defaults are hardcoded to match the DeepFellow
    workspace installer's manual setup script; there is no `--template` option in this version.

    This is a one-shot command: it does not track progress and cannot resume after a partial failure.
    A failure partway through must be recovered manually, or by continuing with individual
    `infra`/`server` subcommands.

    Args:
        admin_name: Admin user's name. Prompted interactively if not given.
        admin_email: Admin user's email. Prompted interactively if not given.
        admin_password: Admin user's password. Prompted interactively if not given.

    Raises:
        InstallError: If any step fails.
    """
    infra_url = f"http://localhost:{DF_INFRA_PORT}"
    server_url = f"http://localhost:{DF_SERVER_PORT}"

    # Resolved once, up front: create-admin and login must use the exact same credentials, so the
    # admin created in step 9 can actually log in during step 10 (create_admin() prompts internally
    # but never returns what it prompted for).
    name = admin_name or echo.prompt_until_valid("Provide admin name", validate_truthy)
    email = admin_email or echo.prompt_until_valid("Provide admin email", validate_email)

    if not admin_password:
        echo.info(PASSWORD_REQUIREMENTS)
    password = admin_password or echo.prompt_until_valid("Provide admin password", validate_password, password=True)

    _run_step(1, "infra install", infra_install)
    _run_step(2, "infra start", lambda: _start_infra())
    _run_step(
        3,
        "infra service install (ollama)",
        lambda: infra_service_install(name="ollama", server=infra_url, spec=json.dumps(OLLAMA_SERVICE_SPEC)),
    )
    _run_step(
        4,
        f"infra model install (chat: {CHAT_MODEL})",
        lambda: infra_model_install(service_name="ollama", model_name=CHAT_MODEL, server=infra_url),
    )
    _run_step(
        5,
        f"infra model install (embedding: {EMBEDDING_MODEL})",
        lambda: infra_model_install(service_name="ollama", model_name=EMBEDDING_MODEL, server=infra_url),
    )
    _run_step(
        6,
        f"infra model install (fast: {FAST_MODEL})",
        lambda: infra_model_install(service_name="ollama", model_name=FAST_MODEL, server=infra_url),
    )
    _run_step(7, "server install", lambda: _server_install())
    _run_step(8, "server start", lambda: _start_server())
    _run_step(9, "create admin", lambda: create_admin(DF_SERVER_DIRECTORY, name, email, password))

    token = _run_step(
        10,
        "server login",
        lambda: get_token_from_login(state.cli_secrets_file, server_url, email=email, password=password),
    )

    workspace: Workspace = _run_step(
        11,
        "workspace creation",
        lambda: create_workspace(
            server_url, token, WORKSPACE_ORGANIZATION_NAME, WORKSPACE_PROJECT_NAME, WORKSPACE_API_KEY_NAME
        ),
    )

    echo.success("DeepFellow workspace installed successfully.")
    echo.info(str(workspace))


def _start_infra() -> None:
    check_infra_directory(DF_INFRA_DIRECTORY)
    start_infra(DF_INFRA_DIRECTORY)


def _start_server() -> None:
    check_server_directory(DF_SERVER_DIRECTORY)
    start_server(DF_SERVER_DIRECTORY)


def _server_install() -> None:
    infra_api_key = env_get(DF_INFRA_DIRECTORY / ".env", "DF_INFRA_API_KEY")
    if not infra_api_key:
        raise InstallError(
            f"DF_INFRA_API_KEY not found in {DF_INFRA_DIRECTORY / '.env'}; cannot configure Server-Infra auth."
        )

    server_install(
        infra_api_key=infra_api_key,
        vectordb_type=VectorDBTypeChoice.milvus,
        embedding_model=EMBEDDING_MODEL,
        embedding_size=str(EMBEDDING_SIZE),
    )
    set_default_server_directory(DF_SERVER_DIRECTORY, force=False)
