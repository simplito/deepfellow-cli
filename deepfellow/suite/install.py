# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Install suite typer command."""

from pathlib import Path
from typing import Annotated

import typer

from deepfellow.common.defaults import (
    DEFAULT_NIGHTSHIFT_MODE,
    DF_FALKORDB_URL,
    DF_INFRA_DIRECTORY,
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_PORT,
    DF_INFRA_STORAGE_DIR,
    DF_MONGO_PORT,
    DF_RABBITMQ_URL,
    DF_SERVER_DIRECTORY,
    DF_SERVER_PORT,
    DF_WORKSPACE_DIRECTORY,
    DF_WORKSPACE_IMAGE,
    DF_WORKSPACE_PORT,
    DF_WORKSPACE_SMALL_MODEL,
    NightshiftModeChoice,
)
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import InstallError, reraise_if_debug
from deepfellow.common.validation import (
    validate_bind_address,
    validate_email,
    validate_mongo_url,
    validate_origin,
    validate_origins,
    validate_password,
    validate_redis_url,
)
from deepfellow.infra.utils.templates import BUILTIN_TEMPLATES as INFRA_BUILTIN_TEMPLATES
from deepfellow.server.utils.templates import BUILTIN_TEMPLATES as SERVER_BUILTIN_TEMPLATES
from deepfellow.suite.utils.install import install as install_util
from deepfellow.workspace.utils.validation import validate_mcp_auth_token

app = typer.Typer()

# Unlike infra install's/server install's own --template, suite install only accepts a built-in
# template name - not a path to a YAML template file - since one value is forwarded to both infra's
# and server's own, independently-schemaed template resolution. Only a name recognized by both is
# usable here.
_TEMPLATE_HELP = (
    "Built-in template name (a custom template file is not supported by `suite install`).\n\n"
    f"Built-in templates: ({', '.join(sorted(set(INFRA_BUILTIN_TEMPLATES) & set(SERVER_BUILTIN_TEMPLATES)))})"
)

# get_parameter_source() returns typer's own vendored ParameterSource enum (typer._click.core),
# not click.core's public one, so comparing by name is what actually works across typer versions
# without reaching into that private module.
_EXPLICIT_PARAMETER_SOURCE_NAMES = frozenset({"COMMANDLINE", "ENVIRONMENT"})

# Every suite-level config flag whose parameter source is worth tracking - see install_util()'s
# docstring for its two independent uses: mapping the "infra_port"/"server_port"/"docker_network"
# subset onto infra's/server's own "port"/"docker_network" `_MERGEABLE_FIELDS` keys for
# template-merge precedence, and warning (for any of them) when an explicitly-passed flag had no
# effect because its install step was already done and skipped.
_EXPLICITLY_PROVIDED_FIELDS = frozenset(
    {
        "infra_port",
        "infra_bind_address",
        "infra_image",
        "infra_local_image",
        "infra_directory",
        "infra_docker_config",
        "infra_storage",
        "server_port",
        "server_bind_address",
        "server_image",
        "server_local_image",
        "server_directory",
        "docker_network",
        "mongodb_port",
        "mongodb_username",
        "mongodb_password",
        "falkordb_active",
        "falkordb_url",
        "falkordb_username",
        "falkordb_password",
        "nightshift_mode",
        "nightshift_start",
        "nightshift_stop",
        "rabbitmq_url",
        "rabbitmq_username",
        "rabbitmq_password",
        "otel_local",
        "workspace_directory",
        "workspace_port",
        "workspace_bind_address",
        "workspace_image",
        "workspace_local_image",
        "workspace_public_url",
        "workspace_small_model",
        "workspace_mongodb_url",
        "workspace_mongodb_database_name",
        "workspace_redis_url",
        "workspace_smtp_host",
        "workspace_smtp_port",
        "workspace_smtp_secure",
        "workspace_smtp_username",
        "workspace_smtp_password",
        "workspace_email_from_address",
        "workspace_email_from_name",
        "workspace_trusted_proxy",
        "workspace_trusted_origins",
        "workspace_mcp_auth_token",
        "workspace_admin_name",
        "workspace_admin_email",
        "workspace_admin_password",
    }
)


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
    resume: bool = typer.Option(
        False, "--resume", help="Continue a previous, incomplete `suite install` run instead of starting fresh."
    ),
    template: str = typer.Option("suite", help=_TEMPLATE_HELP),
    infra_port: int = typer.Option(
        DF_INFRA_PORT, envvar="DF_INFRA_PORT", help="Published port to serve the DeepFellow Infra from."
    ),
    infra_bind_address: str | None = typer.Option(
        None,
        envvar="DF_INFRA_BIND_ADDRESS",
        callback=validate_bind_address,
        help='Host address to publish the Infra port on, e.g. 127.0.0.1. Default: all interfaces ("").',
    ),
    infra_image: str | None = typer.Option(
        None,
        envvar="DF_INFRA_IMAGE",
        help="DeepFellow Infra docker image with a version tag. Default: the newest release compatible with this CLI.",
    ),
    infra_local_image: bool = typer.Option(
        False, help="Use locally build DeepFellow Infra docker image. Requires an explicit tag in --infra-image."
    ),
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
    server_bind_address: str | None = typer.Option(
        None,
        envvar="DF_SERVER_BIND_ADDRESS",
        callback=validate_bind_address,
        help='Host address to publish the Server port on, e.g. 127.0.0.1. Default: all interfaces ("").',
    ),
    server_image: str | None = typer.Option(
        None,
        envvar="DF_SERVER_IMAGE",
        help="DeepFellow Server docker image with a version tag. Default: the newest release compatible with this CLI.",
    ),
    server_local_image: bool = typer.Option(
        False, help="Use locally build DeepFellow Server docker image. Requires an explicit tag in --server-image."
    ),
    skip_version_check: Annotated[
        bool,
        typer.Option(
            "--skip-version-check",
            help="Install images not verified against the CLI version (for development).",
        ),
    ] = False,
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
    nightshift_mode: NightshiftModeChoice = typer.Option(
        DEFAULT_NIGHTSHIFT_MODE, help="Nightshift worker operating mode."
    ),
    nightshift_start: str = typer.Option(
        "", help="Hour Nightshift worker should start (HH:MM, host timezone). Only used with shift mode."
    ),
    nightshift_stop: str = typer.Option(
        "", help="Hour Nightshift worker should stop (HH:MM, host timezone). Only used with shift mode."
    ),
    rabbitmq_url: str = typer.Option(DF_RABBITMQ_URL, help="The host:port for the RabbitMQ instance"),
    rabbitmq_username: str = typer.Option("", help="Username for RabbitMQ authentication"),
    rabbitmq_password: str = typer.Option("", help="Password for RabbitMQ authentication"),
    otel_local: bool = typer.Option(False, "--otel-local", help="Install a local debug-only OpenTelemetry collector."),
    allow_rootful: bool = typer.Option(False, help="Allow rootful Docker without asking user for permission"),
    workspace_directory: Path = typer.Option(
        DF_WORKSPACE_DIRECTORY,
        envvar="DF_WORKSPACE_DIRECTORY",
        help="Target directory for the DeepFellow Workspace installation.",
    ),
    workspace_port: int | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_PORT",
        min=1,
        max=65535,
        help=f"Port to serve Workspace from. Default: {DF_WORKSPACE_PORT}.",
    ),
    workspace_public_url: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_PUBLIC_URL",
        callback=validate_origin,
        help="Origin browsers reach Workspace at; asked for when not given (unless --yes or --non-interactive). "
        "Only a public https:// origin makes DeepFellow Server notify Workspace when files finish indexing.",
    ),
    workspace_bind_address: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_BIND_ADDRESS",
        callback=validate_bind_address,
        help='Host address to publish the Workspace port on, e.g. 127.0.0.1. Default: all interfaces ("").',
    ),
    workspace_image: str = typer.Option(
        DF_WORKSPACE_IMAGE, envvar="DF_WORKSPACE_IMAGE", help="DeepFellow Workspace docker image."
    ),
    workspace_local_image: bool = typer.Option(False, help="Use locally build DeepFellow Workspace docker image."),
    workspace_small_model: str = typer.Option(
        DF_WORKSPACE_SMALL_MODEL,
        envvar="DF_WORKSPACE_SMALL_MODEL",
        help="Model served by DeepFellow Server that Workspace uses for background tasks (session titles, "
        "suggestions, ...). It has to be one of the models granted to the workspace project.",
    ),
    workspace_mongodb_url: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_MONGO_DB_URL",
        callback=validate_mongo_url,
        help="Use this external MongoDB (a replica set) for Workspace instead of installing one.",
    ),
    workspace_mongodb_database_name: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_MONGO_DB_NAME",
        help="Database name in the external Workspace MongoDB; overrides the one in --workspace-mongodb-url.",
    ),
    workspace_redis_url: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_REDIS_URL",
        callback=validate_redis_url,
        help="Use this external Redis for Workspace instead of installing one.",
    ),
    workspace_smtp_host: str | None = typer.Option(
        None, envvar="DF_WORKSPACE_SMTP_HOST", help="Workspace SMTP server host, to send e-mails."
    ),
    workspace_smtp_port: int | None = typer.Option(
        None, envvar="DF_WORKSPACE_SMTP_PORT", min=1, max=65535, help="Workspace SMTP server port. Default: 587."
    ),
    workspace_smtp_secure: bool | None = typer.Option(
        None,
        "--workspace-smtp-secure/--no-workspace-smtp-secure",
        envvar="DF_WORKSPACE_SMTP_SECURE",
        help="Use TLS from the start of the Workspace SMTP connection (usually with port 465). Default: no.",
    ),
    workspace_smtp_username: str | None = typer.Option(
        None, envvar="DF_WORKSPACE_SMTP_USERNAME", help="Workspace SMTP username."
    ),
    workspace_smtp_password: str | None = typer.Option(
        None, envvar="DF_WORKSPACE_SMTP_PASSWORD", help="Workspace SMTP password."
    ),
    workspace_email_from_address: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_EMAIL_FROM_ADDRESS",
        callback=validate_email,
        help="Workspace sender e-mail address.",
    ),
    workspace_email_from_name: str | None = typer.Option(
        None, envvar="DF_WORKSPACE_EMAIL_FROM_NAME", help="Workspace sender name."
    ),
    workspace_trusted_proxy: bool | None = typer.Option(
        None,
        "--workspace-trusted-proxy/--no-workspace-trusted-proxy",
        envvar="DF_WORKSPACE_TRUSTED_PROXY_ENABLED",
        help="Trust X-Forwarded-For / X-Real-IP in Workspace; enable only behind a reverse proxy that sets them. "
        "Default: on for an https --workspace-public-url.",
    ),
    workspace_trusted_origins: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_TRUSTED_ORIGINS",
        callback=validate_origins,
        help="Other origins Workspace trusts besides --workspace-public-url, comma-separated (e.g. more addresses "
        "of the reverse proxy).",
    ),
    workspace_mcp_auth_token: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_MCP_AUTH_TOKEN",
        callback=validate_mcp_auth_token,
        help="Require this bearer token (min 16 characters) on Workspace's /mcp endpoint.",
    ),
    workspace_admin_name: str | None = typer.Option(
        None,
        "--workspace-admin-name",
        envvar="DF_WORKSPACE_BOOTSTRAP_ADMIN_NAME",
        help="Name of the initial Workspace admin, a separate account from the Server admin. Asked when not given.",
    ),
    workspace_admin_email: str | None = typer.Option(
        None,
        "--workspace-admin-email",
        envvar="DF_WORKSPACE_BOOTSTRAP_ADMIN_EMAIL",
        callback=validate_email,
        help="E-mail of the initial Workspace admin (may be the Server admin's). Asked when not given.",
    ),
    workspace_admin_password: str | None = typer.Option(
        None,
        "--workspace-admin-password",
        envvar="DF_WORKSPACE_BOOTSTRAP_ADMIN_PASSWORD",
        callback=validate_password,
        help="Password of the initial Workspace admin; must differ from --admin-password. Asked when not given.",
    ),
) -> None:
    """Provision a complete DeepFellow suite: Infra, Server, admin user, a project, and Workspace.

    Runs a sequence of granular steps, in order: infra configuration, server configuration, infra
    install, infra start, one step per service/model the resolved `--template` installs (the
    "suite" template installs the Ollama service and 3 models), server install, server start, one
    step per post-start action the resolved `--template` runs on server (the "suite" template
    creates the admin account), server login, one call to the server's atomic workspace-creation endpoint
    (organization "Workspace", project "Default", API key "app"), and a follow-up call granting the
    created project access to exactly the models the resolved template installed, then installs
    DeepFellow Workspace with that project's API key. The three
    configuration steps resolve and persist every infra, server and Workspace prompt (directory-overwrite
    decisions, DF_NAME, MongoDB, vector DB, OTel, FalkorDB, the Workspace address, ...) before any of the later,
    apply-only steps run, so all questions are answered once at the start instead of partway
    through a long-running install.

    `--template <name>` selects the built-in template forwarded to both infra's and server's own
    configuration/post-start-action resolution (default `suite`); unlike `infra install`'s/
    `server install`'s own `--template`, only a built-in name is accepted, not a path to a custom
    template file. A `--resume` (or a declined discard) always reuses the template the run being
    continued was originally started with, warning if `--template` was passed with a different
    value - so infra/server configuration and the services/models actually installed can never end
    up resolved from two different templates.

    Progress is persisted after each step; if a step fails, re-run with
    `--resume` to skip every already-completed step and continue from the first incomplete one.
    Re-running without `--resume` over an unfinished previous run asks for confirmation before
    discarding it and starting fresh (skipped by `--yes`, and defaulting to fresh in
    `--non-interactive` mode); declining continues the previous run instead, exactly as `--resume`
    would. Pass `--force-install` to reinstall over an already-existing infra/server directory
    instead of being asked to confirm.

    The Docker socket is checked before any prompt: if it belongs to rootful Docker, the command
    warns and asks whether to continue. Pass `--allow-rootful` to continue without being asked.

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
            resume=resume,
            template=template,
            infra_port=infra_port,
            infra_bind_address=infra_bind_address,
            infra_image=infra_image,
            infra_local_image=infra_local_image,
            infra_directory=infra_directory,
            infra_docker_config=infra_docker_config,
            infra_storage=infra_storage,
            server_port=server_port,
            server_bind_address=server_bind_address,
            server_image=server_image,
            server_local_image=server_local_image,
            skip_version_check=skip_version_check,
            server_directory=server_directory,
            docker_network=docker_network,
            mongodb_port=mongodb_port,
            mongodb_username=mongodb_username,
            mongodb_password=mongodb_password,
            falkordb_active=falkordb_active,
            falkordb_url=falkordb_url,
            falkordb_username=falkordb_username,
            falkordb_password=falkordb_password,
            nightshift_mode=NightshiftModeChoice(nightshift_mode).value,
            nightshift_start=nightshift_start,
            nightshift_stop=nightshift_stop,
            rabbitmq_url=rabbitmq_url,
            rabbitmq_username=rabbitmq_username,
            rabbitmq_password=rabbitmq_password,
            otel_local=otel_local,
            allow_rootful=allow_rootful,
            explicitly_provided=explicitly_provided,
            workspace_directory=workspace_directory,
            workspace_port=workspace_port,
            workspace_public_url=workspace_public_url,
            workspace_bind_address=workspace_bind_address,
            workspace_image=workspace_image,
            workspace_local_image=workspace_local_image,
            workspace_small_model=workspace_small_model,
            workspace_mongodb_url=workspace_mongodb_url,
            workspace_mongodb_database_name=workspace_mongodb_database_name,
            workspace_redis_url=workspace_redis_url,
            workspace_smtp_host=workspace_smtp_host,
            workspace_smtp_port=workspace_smtp_port,
            workspace_smtp_secure=workspace_smtp_secure,
            workspace_smtp_username=workspace_smtp_username,
            workspace_smtp_password=workspace_smtp_password,
            workspace_email_from_address=workspace_email_from_address,
            workspace_email_from_name=workspace_email_from_name,
            workspace_trusted_proxy=workspace_trusted_proxy,
            workspace_trusted_origins=workspace_trusted_origins,
            workspace_mcp_auth_token=workspace_mcp_auth_token,
            workspace_admin_name=workspace_admin_name,
            workspace_admin_email=workspace_admin_email,
            workspace_admin_password=workspace_admin_password,
        )
    except InstallError as exc:
        echo.error(str(exc))
        reraise_if_debug(exc)
