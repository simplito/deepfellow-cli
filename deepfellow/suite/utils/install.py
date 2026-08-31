# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install suite core logic."""

from collections.abc import Callable, Collection
from pathlib import Path
from typing import Any

import typer

from deepfellow.common.defaults import (
    DF_FALKORDB_URL,
    DF_INFRA_DIRECTORY,
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_IMAGE,
    DF_INFRA_PORT,
    DF_INFRA_STORAGE_DIR,
    DF_MONGO_PORT,
    DF_SERVER_DIRECTORY,
    DF_SERVER_IMAGE,
    DF_SERVER_PORT,
)
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get
from deepfellow.common.exceptions import InstallError, translate_to_install_error
from deepfellow.common.install import assert_docker, resolve_admin_kwargs, validate_non_interactive_admin_values
from deepfellow.common.state import state
from deepfellow.common.validation import PASSWORD_REQUIREMENTS, validate_email, validate_password, validate_truthy
from deepfellow.infra.utils.install import install as infra_install
from deepfellow.infra.utils.templates import CHAT_MODEL, EMBEDDING_MODEL, FAST_MODEL
from deepfellow.server.project.utils import update_project
from deepfellow.server.utils.install import install as server_install
from deepfellow.server.utils.login import get_token_from_login
from deepfellow.server.utils.options import set_default_server_directory
from deepfellow.server.utils.workspace import Workspace, create_workspace

WORKSPACE_ORGANIZATION_NAME = "Workspace"
WORKSPACE_PROJECT_NAME = "Default"
WORKSPACE_API_KEY_NAME = "app"

TOTAL_STEPS = 5


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
    force_install: bool = False,
    infra_port: int = DF_INFRA_PORT,
    infra_image: str = DF_INFRA_IMAGE,
    infra_local_image: bool = False,
    infra_directory: Path = DF_INFRA_DIRECTORY,
    infra_docker_config: Path | None = None,
    infra_storage: Path = DF_INFRA_STORAGE_DIR,
    server_port: int = DF_SERVER_PORT,
    server_image: str = DF_SERVER_IMAGE,
    server_local_image: bool = False,
    server_directory: Path = DF_SERVER_DIRECTORY,
    docker_network: str = DF_INFRA_DOCKER_NETWORK,
    mongodb_port: int = DF_MONGO_PORT,
    mongodb_username: str = "",
    mongodb_password: str = "",
    falkordb_active: bool = False,
    falkordb_url: str = DF_FALKORDB_URL,
    falkordb_username: str = "",
    falkordb_password: str = "",
    otel_local: bool = False,
    explicitly_provided: Collection[str] = frozenset(),
) -> None:
    """Provision a complete DeepFellow workspace: Infra, Server, admin user, and a ready-to-use workspace.

    Runs, in order: infra install (via the built-in `workspace` template, which also starts infra
    and installs the ollama service plus chat/embedding/fast models), server install (via the
    built-in `workspace` template, which also starts server and creates the admin user), server
    login, one call to the server's atomic workspace-creation endpoint, and a follow-up call
    granting the created project access to the three models just installed. `suite install` itself
    exposes no `--template` option - it always uses each command's built-in `workspace` template.

    This is a one-shot command: it does not track progress and cannot resume after a partial failure.
    A failure partway through must be recovered manually, or by continuing with individual
    `infra`/`server` subcommands.

    Args:
        admin_name: Admin user's name. Prompted interactively if not given.
        admin_email: Admin user's email. Prompted interactively if not given.
        admin_password: Admin user's password. Prompted interactively if not given.
        force_install: Force a reinstall over an already-existing infra/server directories.
        infra_port: Published port to serve the DeepFellow Infra from.
        infra_image: DeepFellow Infra docker image.
        infra_local_image: Whether to use a locally built DeepFellow Infra docker image.
        infra_directory: Target directory for the DeepFellow Infra installation.
        infra_docker_config: Path to the docker config used to pull the infra image.
        infra_storage: Storage directory for the DeepFellow Infra services.
        server_port: Port to use to serve the DeepFellow Server from.
        server_image: DeepFellow Server docker image.
        server_local_image: Whether to use a locally built DeepFellow Server docker image.
        server_directory: Target directory for the DeepFellow Server installation.
        docker_network: The Docker network name shared by infra and server.
        mongodb_port: Host port to publish the locally-managed MongoDB on.
        mongodb_username: Username for the locally-managed MongoDB's authentication.
        mongodb_password: Password for the locally-managed MongoDB's authentication.
        falkordb_active: Whether to enable the Knowledge Graph (FalkorDB) instance.
        falkordb_url: The host:port for the FalkorDB instance.
        falkordb_username: Username for FalkorDB authentication.
        falkordb_password: Password for FalkorDB authentication.
        otel_local: Whether to install a local debug-only OpenTelemetry collector.
        explicitly_provided: The subset of `{"infra_port", "server_port", "docker_network"}` whose
            CLI option was actually passed on the command line or via envvar - the only suite-level
            fields that also participate in infra's or server's own template-value merging. Mapped
            here onto infra's and server's own "port"/"docker_network" `_MERGEABLE_FIELDS` keys.

    Raises:
        InstallError: If Docker is missing/unusable, if any step fails, or if --non-interactive is
            set and an admin name, email, or password is missing.
    """
    # Checked before any prompting: infra install's own inspect() checks this too, but only once
    # step 1 actually runs, which is after the admin-credential prompts below. Checking it here
    # avoids making the user answer those prompts just to hit an unrelated Docker failure right
    # after.
    assert_docker()

    # No action_kwargs source here (unlike server install's create_admin post-start action) - {} makes
    # the CLI flags the only source, which is what suite install has ever supported.
    effective = resolve_admin_kwargs({}, admin_name, admin_email, admin_password)
    validate_non_interactive_admin_values(effective, "suite install")

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

    infra_explicitly_provided = {"port"} if "infra_port" in explicitly_provided else set()
    if "docker_network" in explicitly_provided:
        infra_explicitly_provided.add("docker_network")

    server_explicitly_provided = {"port"} if "server_port" in explicitly_provided else set()
    if "docker_network" in explicitly_provided:
        server_explicitly_provided.add("docker_network")

    _run_step(
        1,
        "infra install",
        lambda: infra_install(
            template="workspace",
            force_install=force_install,
            port=infra_port,
            image=infra_image,
            local_image=infra_local_image,
            directory=infra_directory,
            docker_config=infra_docker_config,
            storage=infra_storage,
            docker_network=docker_network,
            explicitly_provided=infra_explicitly_provided,
        ),
    )
    _run_step(
        2,
        "server install",
        lambda: _server_install(
            name,
            email,
            password,
            force_install,
            infra_directory=infra_directory,
            port=server_port,
            image=server_image,
            local_image=server_local_image,
            directory=server_directory,
            docker_network=docker_network,
            mongodb_port=mongodb_port,
            mongodb_username=mongodb_username,
            mongodb_password=mongodb_password,
            falkordb_active=falkordb_active,
            falkordb_url=falkordb_url,
            falkordb_username=falkordb_username,
            falkordb_password=falkordb_password,
            otel_local=otel_local,
            explicitly_provided=server_explicitly_provided,
        ),
    )

    # Read back the port server install actually resolved - not server_port, which _resolve_port()
    # (deepfellow/server/utils/install.py) silently overrides with a prior install's own DF_SERVER_PORT
    # whenever "port" isn't in server_explicitly_provided, e.g. on a re-run against a directory that
    # already has a different port configured. The CLI process runs outside Docker, so this must be
    # localhost, not a docker-network hostname. No default= here: server install (which just
    # succeeded) always writes DF_SERVER_PORT to this .env, so a missing file/key means something
    # is genuinely broken - env_get's own should_raise=True default is the right behavior, not a
    # case to silently paper over with the raw --server-port value.
    resolved_server_port = env_get(server_directory / ".env", "DF_SERVER_PORT")
    server_url = f"http://localhost:{resolved_server_port}"

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

    _run_step(
        5,
        "grant model access",
        lambda: update_project(
            server_url,
            token,
            workspace.organization.id,
            workspace.project.id,
            {"models": [CHAT_MODEL, EMBEDDING_MODEL, FAST_MODEL]},
        ),
    )

    echo.success("DeepFellow workspace installed successfully.")
    echo.info(str(workspace))


def _server_install(
    name: str,
    email: str,
    password: str,
    force_install: bool,
    *,
    infra_directory: Path,
    port: int,
    image: str,
    local_image: bool,
    directory: Path,
    docker_network: str,
    mongodb_port: int,
    mongodb_username: str,
    mongodb_password: str,
    falkordb_active: bool,
    falkordb_url: str,
    falkordb_username: str,
    falkordb_password: str,
    otel_local: bool,
    explicitly_provided: Collection[str],
) -> None:
    infra_api_key = env_get(infra_directory / ".env", "DF_INFRA_API_KEY")
    if not infra_api_key:
        raise InstallError(
            f"DF_INFRA_API_KEY not found in {infra_directory / '.env'}; cannot configure Server-Infra auth."
        )
    # Always explicit: this key was just read from the infra suite itself installed, so it must
    # never be silently outranked by a template's own "infra_api_key" - unlike port/docker_network,
    # this isn't conditional on a suite CLI flag being passed, since suite is the one deciding it.
    explicitly_provided = set(explicitly_provided) | {"infra_api_key"}

    server_install(
        template="workspace",
        infra_api_key=infra_api_key,
        admin_name=name,
        admin_email=email,
        admin_password=password,
        force_install=force_install,
        port=port,
        image=image,
        local_image=local_image,
        directory=directory,
        docker_network=docker_network,
        mongodb_port=mongodb_port,
        mongodb_username=mongodb_username,
        mongodb_password=mongodb_password,
        falkordb_active=falkordb_active,
        falkordb_url=falkordb_url,
        falkordb_username=falkordb_username,
        falkordb_password=falkordb_password,
        otel_local=otel_local,
        explicitly_provided=explicitly_provided,
    )
    set_default_server_directory(directory, force=False)
