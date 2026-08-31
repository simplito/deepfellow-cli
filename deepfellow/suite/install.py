# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install suite typer command."""

from pathlib import Path

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
from deepfellow.common.exceptions import InstallError, reraise_if_debug
from deepfellow.common.validation import validate_email, validate_password
from deepfellow.suite.utils.install import install as install_util

app = typer.Typer()

# get_parameter_source() returns typer's own vendored ParameterSource enum (typer._click.core),
# not click.core's public one, so comparing by name is what actually works across typer versions
# without reaching into that private module.
_EXPLICIT_PARAMETER_SOURCE_NAMES = frozenset({"COMMANDLINE", "ENVIRONMENT"})

# The only suite-level flags that also participate in either infra's or server's own
# _MERGEABLE_FIELDS (template-value merging) - see install_util()'s docstring for how these map
# onto infra's and server's own "port"/"docker_network" keys.
_EXPLICITLY_PROVIDED_FIELDS = frozenset({"infra_port", "server_port", "docker_network"})


def _resolve_server_directory(value: Path) -> Path:
    """Resolve --server-directory to an absolute path before it can reach `set_default_server_directory()`.

    Mirrors `deepfellow.server.utils.options.default_directory_callback`'s own unconditional
    `.resolve()` - a relative path here would otherwise get persisted as-is into
    ~/.deepfellow/config's DF_DEFAULT_SERVER_DIR, breaking any later `server` command run from a
    different working directory.
    """
    return value.resolve()


@app.command()
def install(
    ctx: typer.Context,
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
    infra_port: int = typer.Option(
        DF_INFRA_PORT, envvar="DF_INFRA_PORT", help="Published port to serve the DeepFellow Infra from."
    ),
    infra_image: str = typer.Option(DF_INFRA_IMAGE, envvar="DF_INFRA_IMAGE", help="DeepFellow Infra docker image."),
    infra_local_image: bool = typer.Option(False, help="Use locally build DeepFellow Infra docker image."),
    infra_directory: Path = typer.Option(
        DF_INFRA_DIRECTORY,
        envvar="DF_INFRA_DIRECTORY",
        help="Target directory for the DeepFellow Infra installation.",
    ),
    infra_docker_config: Path | None = typer.Option(
        None, envvar="DF_INFRA_DOCKER_CONFIG", help="Path to the docker config."
    ),
    infra_storage: Path = typer.Option(
        DF_INFRA_STORAGE_DIR, envvar="DF_INFRA_STORAGE_DIR", help="Storage for the DeepFellow Infra services."
    ),
    server_port: int = typer.Option(
        DF_SERVER_PORT, envvar="DF_SERVER_PORT", help="Port to use to serve the DeepFellow Server from."
    ),
    server_image: str = typer.Option(DF_SERVER_IMAGE, envvar="DF_SERVER_IMAGE", help="DeepFellow Server docker image."),
    server_local_image: bool = typer.Option(False, help="Use locally build DeepFellow Server docker image."),
    server_directory: Path = typer.Option(
        DF_SERVER_DIRECTORY,
        envvar="DF_SERVER_DIRECTORY",
        callback=_resolve_server_directory,
        help="Target directory for the DeepFellow Server installation. Note: server storage (config.json, "
        "uploads) is shared globally across all installs on this machine and is not isolated per directory.",
    ),
    docker_network: str = typer.Option(
        DF_INFRA_DOCKER_NETWORK,
        envvar="DF_INFRA_DOCKER_NETWORK",
        help="The Docker network name shared by infra and server, for container communication.",
    ),
    mongodb_port: int = typer.Option(DF_MONGO_PORT, help="Host port to publish the local MongoDB on."),
    mongodb_username: str = typer.Option("", help="Username for MongoDB authentication"),
    mongodb_password: str = typer.Option("", help="Password for MongoDB authentication"),
    falkordb_active: bool = typer.Option(False, help="Enable the Knowledge Graph (FalkorDB) instance."),
    falkordb_url: str = typer.Option(DF_FALKORDB_URL, help="The host:port for the FalkorDB instance"),
    falkordb_username: str = typer.Option("", help="Username for FalkorDB authentication"),
    falkordb_password: str = typer.Option("", help="Password for FalkorDB authentication"),
    otel_local: bool = typer.Option(False, "--otel-local", help="Install a local debug-only OpenTelemetry collector."),
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

    Most `infra install`/`server install` options are reachable interactively through the prompts
    this command already triggers under the hood; the options above only cover values that have no
    interactive path.
    """
    # merged[key] != own_default can't tell an explicitly-passed flag from an unpassed one when the
    # two happen to be equal (e.g. an explicit `--infra-port 8086` where 8086 is also its own
    # default) - ctx.get_parameter_source() is the only way to know for sure, so it's computed here,
    # once, from the live Click invocation, and handed to install_util() instead of being re-derived
    # from values.
    explicitly_provided = {
        key
        for key in _EXPLICITLY_PROVIDED_FIELDS
        if (source := ctx.get_parameter_source(key)) is not None and source.name in _EXPLICIT_PARAMETER_SOURCE_NAMES
    }
    try:
        install_util(
            admin_name=admin_name,
            admin_email=admin_email,
            admin_password=admin_password,
            force_install=force_install,
            infra_port=infra_port,
            infra_image=infra_image,
            infra_local_image=infra_local_image,
            infra_directory=infra_directory,
            infra_docker_config=infra_docker_config,
            infra_storage=infra_storage,
            server_port=server_port,
            server_image=server_image,
            server_local_image=server_local_image,
            server_directory=server_directory,
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
    except InstallError as exc:
        echo.error(str(exc))
        reraise_if_debug(exc)
