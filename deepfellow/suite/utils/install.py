# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Install suite core logic."""

from collections.abc import Callable, Collection, Mapping
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import Any

import typer

from deepfellow.common.defaults import (
    DEFAULT_NIGHTSHIFT_MODE,
    DEFAULT_VECTOR_DATABASE,
    DEFAULT_VECTOR_DATABASE_TYPE,
    DF_FALKORDB_URL,
    DF_INFRA_DIRECTORY,
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_IMAGE_HUB,
    DF_INFRA_NAME,
    DF_INFRA_PORT,
    DF_INFRA_STORAGE_DIR,
    DF_INFRA_URL,
    DF_MONGO_DB,
    DF_MONGO_PORT,
    DF_MONGO_URL,
    DF_RABBITMQ_URL,
    DF_SERVER_DIRECTORY,
    DF_SERVER_IMAGE_HUB,
    DF_SERVER_PORT,
    DF_SUITE_INSTALL_STATE_FILE,
    DF_WORKSPACE_DIRECTORY,
    DF_WORKSPACE_SMALL_MODEL,
    DOC_CHUNKER_STT_MODEL,
    MILVUS_DATABASE,
    SERVER_CONTAINER_NAME,
    VectorDBTypeChoice,
)
from deepfellow.common.docker import get_socket, is_service_running, local_url
from deepfellow.common.echo import echo, is_interactive
from deepfellow.common.env import env_get
from deepfellow.common.exceptions import DockerNetworkError, InstallError, reraise_if_debug, translate_to_install_error
from deepfellow.common.install import (
    assert_docker,
    ensure_directory,
    resolve_admin_kwargs,
    validate_non_interactive_admin_values,
)
from deepfellow.common.registry import resolve_install_image
from deepfellow.common.state import state
from deepfellow.common.templates import PostStartAction
from deepfellow.common.validation import PASSWORD_REQUIREMENTS, validate_email, validate_password, validate_truthy
from deepfellow.infra.utils.docker import start_infra
from deepfellow.infra.utils.install import InstallConfig as InfraInstallConfig
from deepfellow.infra.utils.install import apply as infra_apply
from deepfellow.infra.utils.install import inspect as infra_inspect
from deepfellow.infra.utils.install import resolve as infra_resolve
from deepfellow.infra.utils.templates import BUILTIN_TEMPLATES as INFRA_BUILTIN_TEMPLATES
from deepfellow.infra.utils.templates import dispatch_post_start_action as infra_dispatch_post_start_action
from deepfellow.infra.utils.templates import resolve_template as infra_resolve_template
from deepfellow.server.organization.utils import Organization
from deepfellow.server.project.api_key.utils import ApiKey
from deepfellow.server.project.utils import Project, update_project
from deepfellow.server.utils.configure import FalkorDBConfig, NightshiftConfig, OtelConfig
from deepfellow.server.utils.docker import start_server
from deepfellow.server.utils.install import InstallConfig as ServerInstallConfig
from deepfellow.server.utils.install import apply as server_apply
from deepfellow.server.utils.install import inspect as server_inspect
from deepfellow.server.utils.install import resolve as server_resolve
from deepfellow.server.utils.login import get_token_from_login
from deepfellow.server.utils.options import set_default_server_directory
from deepfellow.server.utils.templates import BUILTIN_TEMPLATES as SERVER_BUILTIN_TEMPLATES
from deepfellow.server.utils.templates import dispatch_post_start_action as server_dispatch_post_start_action
from deepfellow.server.utils.templates import resolve_template as server_resolve_template
from deepfellow.server.utils.users import create_admin as create_admin_util
from deepfellow.server.utils.workspace import Workspace, create_workspace
from deepfellow.suite.utils.state import SuiteInstallState
from deepfellow.suite.utils.state import delete as delete_state
from deepfellow.suite.utils.state import load as load_state
from deepfellow.suite.utils.state import save as save_state
from deepfellow.suite.utils.vram import print_vram_estimate
from deepfellow.workspace.install import install_workspace
from deepfellow.workspace.utils.install import (
    confirm_overwrite,
    incomplete_groups,
    read_existing_env,
    resolve_stack_settings,
)
from deepfellow.workspace.utils.public_url import (
    PUBLIC_URL_KEY,
    TRUSTED_ORIGINS_KEY,
    TRUSTED_PROXY_KEY,
    apply_https_settings,
    insecure_context_warning,
    resolve_public_url,
)

WORKSPACE_ORGANIZATION_NAME = "Workspace"
WORKSPACE_PROJECT_NAME = "Default"
WORKSPACE_API_KEY_NAME = "app"
# .env keys of an external MongoDB/Redis, which `_workspace_install()` forgets so the bundled ones are used.
_WORKSPACE_LOCAL_SERVICE_KEYS = ("MONGO_DB_URL", "MONGO_DB_NAME", "REDIS_URL")
# DeepFellow Server as the Workspace container reaches it, on the Docker network shared with Server.
_SERVER_URL_IN_DOCKER_NETWORK = f"http://{SERVER_CONTAINER_NAME}:{DF_SERVER_PORT}/v1"
# Steps asking and installing Workspace; see `_build_steps()`.
STEP_WORKSPACE_CONFIG = "workspace_config"
STEP_WORKSPACE_INSTALL = "workspace_install"
# Asked for up front by STEP_WORKSPACE_CONFIG; the rest is only read by STEP_WORKSPACE_INSTALL.
_WORKSPACE_ADMIN_KEYS = ("BOOTSTRAP_ADMIN_NAME", "BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_PASSWORD")
_WORKSPACE_ADDRESS_FIELDS = frozenset(
    {
        "workspace_public_url",
        "workspace_trusted_proxy",
        "workspace_trusted_origins",
        "workspace_admin_name",
        "workspace_admin_email",
        "workspace_admin_password",
    }
)
# Settings saved with the answers above (`SuiteInstallState.workspace_apply`), so they are fixed from the first run.
_WORKSPACE_APPLY_FIELDS = frozenset(
    {
        "workspace_directory",
        "workspace_port",
        "workspace_bind_address",
        "workspace_image",
        "workspace_local_image",
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
        "workspace_mcp_auth_token",
    }
)

# suite install only accepts a built-in template name recognized by BOTH infra and server, since one
# --template value is forwarded to each of their independently-schemaed template resolution
# mechanisms - unlike `infra install --template`/`server install --template`, a YAML template file
# path isn't supported here.
_SUITE_BUILTIN_TEMPLATES = frozenset(INFRA_BUILTIN_TEMPLATES) & frozenset(SERVER_BUILTIN_TEMPLATES)


def _validate_template(template: str) -> None:
    """Reject a --template value suite install doesn't support: anything but a shared built-in name.

    Called before any prompt or installation action, so an unsupported value fails immediately
    instead of surfacing later as a confusing "template file not found" error from
    infra_inspect()'s/server_inspect()'s own resolve_template() file-path fallback.

    Raises:
        InstallError: If `template` is not a member of `_SUITE_BUILTIN_TEMPLATES`.
    """
    if template in _SUITE_BUILTIN_TEMPLATES:
        return
    names = ", ".join(sorted(_SUITE_BUILTIN_TEMPLATES))
    raise InstallError(
        f"'{template}' is not a valid suite install template; suite install only accepts a built-in "
        f"template name (not a path to a template file). Built-in templates: ({names})"
    )


# Canonical step ids, persisted to the state file, and their display names. STEP_INFRA_CONFIG and
# STEP_SERVER_CONFIG resolve infra's and server's configuration (every prompt each one has) before
# any installation action runs - see _infra_config()/_server_config(). The steps between
# STEP_INFRA_START and STEP_SERVER_INSTALL are what a plain `infra install --template <name>` runs
# internally as its post-start actions (minus its own now-separate config/resolve phase); the steps
# between STEP_SERVER_START and STEP_SERVER_LOGIN are what `server install --template <name>` runs
# internally as ITS post-start actions, likewise minus its config phase. suite install drives each
# individually - instead of delegating wholesale to infra_install()/server_install() - so a failure
# at any point (e.g. infra installs fine but fails to start) is trackable and resumable at that
# exact step.
STEP_INFRA_CONFIG = "infra_config"
STEP_SERVER_CONFIG = "server_config"
STEP_INFRA_INSTALL = "infra_install"
STEP_INFRA_START = "infra_start"
STEP_SERVER_INSTALL = "server_install"
STEP_SERVER_START = "server_start"
STEP_SERVER_LOGIN = "server_login"
STEP_WORKSPACE_CREATION = "workspace_creation"
STEP_GRANT_MODEL_ACCESS = "grant_model_access"

# Never granted to the project: Server reaches them only through Doc Chunker (see STEP_GRANT_MODEL_ACCESS).
_DOC_CHUNKER_ONLY_MODELS = frozenset({DOC_CHUNKER_STT_MODEL})


def _infra_post_start_action_step_id(index: int) -> str:
    """Step id for the resolved infra template's post-start action at position `index`."""
    return f"infra_post_start_action_{index}"


def _infra_post_start_action_display_name(action: PostStartAction) -> str:
    """Human-readable display name for one resolved infra template post-start action."""
    label = action["kwargs"].get("model_name") or action["kwargs"].get("name") or ""
    name = action["function"].removeprefix("infra.").replace(".", " ")
    return f"infra {name}" + (f" ({label})" if label else "")


def _server_post_start_action_step_id(index: int) -> str:
    """Step id for the resolved server template's post-start action at position `index`."""
    return f"server_post_start_action_{index}"


def _server_post_start_action_display_name(action: PostStartAction) -> str:
    """Human-readable display name for one resolved server template post-start action."""
    label = action["kwargs"].get("name") or action["kwargs"].get("email") or ""
    name = action["function"].removeprefix("server.").replace("_", " ")
    return name + (f" ({label})" if label else "")


def _build_steps(
    infra_post_start_actions: list[PostStartAction], server_post_start_actions: list[PostStartAction]
) -> tuple[tuple[str, str], ...]:
    """The full, ordered (step id, display name) list for this run.

    One step per entry of the resolved infra template's post_start_actions is inserted between
    STEP_INFRA_START and STEP_SERVER_INSTALL, in order - the "suite" template's 4 actions
    (ollama service + 3 models) are what made this section look fixed before. Likewise, one step per
    entry of the resolved server template's post_start_actions is inserted between STEP_SERVER_START
    and STEP_SERVER_LOGIN - the "suite" template's single server.create_admin action is what made
    that section look fixed before. A different --template's action count changes either list's
    length accordingly, with no other code change needed. Computed once per run (see install()), not
    a module-level constant, since it depends on the resolved --template.
    """
    return (
        (STEP_INFRA_CONFIG, "infra configuration"),
        (STEP_SERVER_CONFIG, "server configuration"),
        (STEP_WORKSPACE_CONFIG, "workspace configuration"),
        (STEP_INFRA_INSTALL, "infra install"),
        (STEP_INFRA_START, "infra start"),
        *(
            (_infra_post_start_action_step_id(i), _infra_post_start_action_display_name(action))
            for i, action in enumerate(infra_post_start_actions)
        ),
        (STEP_SERVER_INSTALL, "server install"),
        (STEP_SERVER_START, "server start"),
        *(
            (_server_post_start_action_step_id(i), _server_post_start_action_display_name(action))
            for i, action in enumerate(server_post_start_actions)
        ),
        (STEP_SERVER_LOGIN, "server login"),
        (STEP_WORKSPACE_CREATION, "workspace creation"),
        (STEP_GRANT_MODEL_ACCESS, "grant model access"),
        (STEP_WORKSPACE_INSTALL, "workspace install"),
    )


# Suite-level config flag names relevant to each install step, used by _warn_config_flags_ignored()
# below - a subset of _EXPLICITLY_PROVIDED_FIELDS (deepfellow/suite/install.py). docker_network is
# in both, since it applies to both infra and server installs.
_INFRA_CONFIG_FIELDS = frozenset(
    {
        "infra_port",
        "infra_bind_address",
        "infra_image",
        "infra_local_image",
        "infra_directory",
        "infra_docker_config",
        "infra_storage",
        "docker_network",
    }
)
_SERVER_CONFIG_FIELDS = frozenset(
    {
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
    }
)


def _step_position(steps: tuple[tuple[str, str], ...], step_id: str) -> tuple[int, str]:
    """Return a step's 1-based position and display name within `steps`."""
    return next((index, name) for index, (id_, name) in enumerate(steps, start=1) if id_ == step_id)


def _install_directory_intact(directory: Path) -> bool:
    """Cheap, local, non-interactive liveness signal for infra_install/server_install.

    Unlike `is_service_running` for the *_start steps, this decides whether a step already marked
    complete still counts as done - it must never gate an always_run-style re-execution, since the
    apply steps it gates rewrite the compose file and re-pull the image every time they run, which
    isn't free to redo on every `--resume` for no reason. If the directory or its `.env` are gone,
    the step is treated as not-done and its apply phase genuinely re-runs, reapplying the config
    already persisted by its own ask-phase step (`_infra_config()`/`_server_config()`) rather than
    resolving (and re-prompting for) a fresh one - `_infra_install_apply()`/`_server_install_apply()`
    themselves handle recreating a fully-deleted directory via `ensure_directory()`.
    """
    return directory.is_dir() and (directory / ".env").is_file()


def _install_still_done(install_state: SuiteInstallState, step_id: str, directory: Path) -> bool:
    """`is_done` for an *_install step(infra or server): was it completed, and does its directory still look intact."""
    return step_id in install_state.completed_steps and _install_directory_intact(directory)


def _start_still_done(install_state: SuiteInstallState, step_id: str, service: str, directory: Path) -> bool:
    """`is_done` for a *_start step(infra or server): was it completed, and is its container still running."""
    return step_id in install_state.completed_steps and is_service_running(service, cwd=directory)


def _warn_config_flags_ignored(
    component: str, explicitly_provided: Collection[str], relevant_fields: Collection[str]
) -> None:
    """Warn when a config flag explicitly passed on this invocation had no effect.

    That happens when `component`'s config step (`STEP_INFRA_CONFIG`/`STEP_SERVER_CONFIG`) was
    already done and skipped outright, reconstructing config from what an earlier run already
    resolved rather than resolving it fresh - the only step these flags are ever read by. Mirrors
    `_server_post_start_action`'s `admin_overridden` warning: an explicit --infra-port/
    --infra-directory/etc. on a `--resume` run against an already-configured component is
    otherwise silently ignored, same as an admin override against an already-existing account.
    """
    overridden = sorted(field for field in explicitly_provided if field in relevant_fields)
    if not overridden:
        return
    flags = ", ".join(f"--{field.replace('_', '-')}" for field in overridden)
    verb = "was" if len(overridden) == 1 else "were"
    echo.warning(
        f"{flags} {verb} ignored: {component} is already installed for this run; its configuration is unchanged."
    )


# The only suite-level flags whose CLI option was actually passed that infra's or server's own
# config step also needs to know about - mapped onto infra's and server's own "port"/
# "docker_network" keys (their template-value merging, _MERGEABLE_FIELDS), per install()'s own
# docstring. "nightshift_mode" is forwarded to server as-is, so an explicit --nightshift-mode
# overrides a stored DF_NIGHTSHIFT_MODE the same way it does for `server install`.
_INFRA_EXPLICIT_KEYS = {"infra_port": "port", "docker_network": "docker_network"}
_SERVER_EXPLICIT_KEYS = {
    "server_port": "port",
    "docker_network": "docker_network",
    "nightshift_mode": "nightshift_mode",
}


def _map_explicitly_provided(explicitly_provided: Collection[str], keys: dict[str, str]) -> set[str]:
    """Translate suite-level explicitly provided flag names into a component's own key names."""
    return {component_key for suite_key, component_key in keys.items() if suite_key in explicitly_provided}


def _infra_config_on_skip(install_state: SuiteInstallState, explicitly_provided: Collection[str]) -> InfraInstallConfig:
    """`on_skip` for `STEP_INFRA_CONFIG`: warn about any now-ineffective flag, then reconstruct.

    A module-level function (not a closure inside `install()`) purely to keep `install()`'s own
    cyclomatic complexity down - it's simple enough to take its two captured values as plain
    arguments via `functools.partial` instead.
    """
    _warn_config_flags_ignored("infra", explicitly_provided, _INFRA_CONFIG_FIELDS)
    return _infra_config_from_dict(install_state.infra_config)  # type: ignore[arg-type]


def _server_config_on_skip(
    install_state: SuiteInstallState, explicitly_provided: Collection[str]
) -> ServerInstallConfig:
    """`on_skip` for `STEP_SERVER_CONFIG` - see `_infra_config_on_skip()`."""
    _warn_config_flags_ignored("server", explicitly_provided, _SERVER_CONFIG_FIELDS)
    return _server_config_from_dict(install_state.server_config)  # type: ignore[arg-type]


def _resolve_effective_template(install_state: SuiteInstallState, template: str) -> str:
    """Reconcile this invocation's `--template` with any persisted template, warning on a mismatch.

    `install_state` continues a run (via `--resume`, or a declined discard - see `install()`)
    instead of starting fresh whenever it already has a persisted template - reused here instead of
    silently mixing the two, since a persisted template always wins over this invocation's own.

    A module-level function (not a closure inside `install()`) purely to keep `install()`'s own
    cyclomatic complexity down - same rationale as `_infra_config_on_skip()`.

    Without this, a `--resume` invocation whose `--template` differs from - or, since it defaults
    to `"suite"`, simply omits - the one the original run configured infra/server against would
    still resolve `infra_post_start_actions`/`granted_models` from *this* invocation's template,
    installing one template's services/models against the other template's configuration, with no
    error or warning.

    Returns:
        The template name `install()` must actually use for the rest of this run. Also writes it
        onto `install_state.template` as a side effect - a no-op when reusing an already-matching
        persisted value, and how a freshly-started `install_state` first records its own template.
    """
    if install_state.template is not None and install_state.template != template:
        echo.warning(
            f"--template {template!r} ignored: this suite install was already started with template "
            f"{install_state.template!r}; reusing it instead of mixing templates between the "
            "infra/server configuration and the services/models this run installs."
        )
        return install_state.template
    install_state.template = template
    return template


def _workspace_to_dict(workspace: Workspace) -> dict[str, Any]:
    """Serialize a Workspace for persistence, including its (get-once, non-recoverable) API key."""
    return {
        "organization": asdict(workspace.organization),
        "project": asdict(workspace.project),
        "api_key": asdict(workspace.api_key),
    }


def _workspace_from_dict(data: dict[str, Any]) -> Workspace:
    """Reconstruct a Workspace from a previously persisted `_workspace_to_dict()` result.

    Raises:
        InstallError: If `data` doesn't have the expected shape - e.g. corrupted by a crash
            mid-write, or the state file was hand-edited. Letting a bare
            KeyError/TypeError/AttributeError escape here would crash with an unhandled traceback
            (unlike every other step's failure, which surfaces as a clean, catchable message) - one
            of three places suite install reconstructs an object straight from unvalidated,
            persisted JSON, alongside `_infra_config_from_dict()`/`_server_config_from_dict()`.
            AttributeError is included because ApiKey.from_data() calls data["api_key"].get(...) -
            a non-dict api_key (e.g. a string or null) raises AttributeError there instead of
            TypeError/KeyError; the other two reconstructors need no such case - see their own
            docstrings.
    """
    try:
        return Workspace(
            organization=Organization(**data["organization"]),
            project=Project(**data["project"]),
            api_key=ApiKey.from_data(data["api_key"]),
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise InstallError(
            "Suite install state file's persisted workspace data is invalid or corrupted; remove "
            f"{DF_SUITE_INSTALL_STATE_FILE} and re-run to start a fresh install."
        ) from exc


def _infra_config_to_dict(config: InfraInstallConfig) -> dict[str, Any]:
    """Serialize infra's resolved InstallConfig for persistence (Path fields become strings)."""
    data = asdict(config)
    data["directory"] = str(config.directory)
    data["docker_config"] = str(config.docker_config)
    data["storage_dir"] = str(config.storage_dir)
    return data


def _infra_config_from_dict(data: dict[str, Any]) -> InfraInstallConfig:
    """Reconstruct infra's InstallConfig from a previously persisted `_infra_config_to_dict()` result.

    Raises:
        InstallError: If `data` doesn't have the expected shape - see `_workspace_from_dict()` for
            why this is handled the same way (unvalidated, persisted JSON reconstructed directly
            into a dataclass). Unlike `_workspace_from_dict()`, no `AttributeError` is possible
            here - reconstruction is plain dataclass `**dict` unpacking with no `.get()`/attribute
            access on an unvalidated sub-value, so malformed data always surfaces as `TypeError`
            (or `KeyError`) instead.
    """
    try:
        return InfraInstallConfig(
            **{
                **data,
                "directory": Path(data["directory"]),
                "docker_config": Path(data["docker_config"]),
                "storage_dir": Path(data["storage_dir"]),
            }
        )
    except (KeyError, TypeError) as exc:
        raise InstallError(
            "Suite install state file's persisted infra configuration is invalid or corrupted; remove "
            f"{DF_SUITE_INSTALL_STATE_FILE} and re-run to start a fresh install."
        ) from exc


def _server_config_to_dict(config: ServerInstallConfig) -> dict[str, Any]:
    """Serialize server's resolved InstallConfig for persistence (Path field becomes a string)."""
    data = asdict(config)
    data["directory"] = str(config.directory)
    return data


def _server_config_from_dict(data: dict[str, Any]) -> ServerInstallConfig:
    """Reconstruct server's InstallConfig from a previously persisted `_server_config_to_dict()` result.

    Raises:
        InstallError: If `data` doesn't have the expected shape - see `_workspace_from_dict()` and
            `_infra_config_from_dict()` for why `AttributeError` isn't caught here either.
    """
    try:
        return ServerInstallConfig(
            **{
                **data,
                "directory": Path(data["directory"]),
                "otel": OtelConfig(**data["otel"]),
                "falkordb": FalkorDBConfig(**data["falkordb"]),
                "nightshift": NightshiftConfig(**data["nightshift"]),
            }
        )
    except (KeyError, TypeError) as exc:
        raise InstallError(
            "Suite install state file's persisted server configuration is invalid or corrupted; remove "
            f"{DF_SUITE_INSTALL_STATE_FILE} and re-run to start a fresh install."
        ) from exc


@translate_to_install_error
def _infra_config(
    force_install: bool,
    *,
    port: int,
    bind_address: str | None = None,
    image: str | None,
    local_image: bool,
    directory: Path,
    docker_config: Path | None,
    storage: Path,
    docker_network: str,
    template: str,
    explicitly_provided: Collection[str],
    allow_rootful: bool,
    docker_socket: str,
    skip_version_check: bool = False,
    checked_image: str | None = None,
) -> InfraInstallConfig:
    """Infra's ask-phase: inspect() + resolve(), collecting every infra-side prompt. No apply.

    Mirrors `deepfellow.infra.utils.install.install()`'s own body for this phase, with the resolved
    `--template` (see `install()`'s own docstring for suite install's built-in-only restriction on
    it), and forwards the config-level flags (port, image, directory, ...) `infra install` itself
    accepts. `docker_socket` is the socket `install()` already resolved (and warned about, if
    rootful) before the admin prompts, so `inspect()` reuses it instead of looking it up - and
    warning - a second time. Decorated the same as every other step function - `translate_to_install_error` now
    propagates a wrapped function's return value unchanged, so this ask-phase function's resolved
    config still reaches its caller, while `OSError`/`typer.BadParameter` raised anywhere in
    `inspect()`/`resolve()` (e.g. from `ensure_directory()`) still
    get translated to a clean `InstallError` right here - exactly like `_infra_install_apply` -
    instead of only being caught much later by `install()`'s own decorator, bypassing `_run_step()`'s
    per-step "Step N/TOTAL (name) failed: ..." message.
    """
    context = infra_inspect(
        directory=directory,
        allow_rootful=allow_rootful,
        force_install=force_install,
        image=image,
        local_image=local_image,
        template=template,
        docker_socket=docker_socket,
        skip_version_check=skip_version_check,
        checked_image=checked_image,
    )
    docker_config = docker_config or directory / "docker-config.json"
    return infra_resolve(
        context,
        port=port,
        docker_config=docker_config,
        storage=storage,
        hugging_face_token=None,
        civitai_token=None,
        infra_name=DF_INFRA_NAME,
        infra_url=DF_INFRA_URL,
        docker_network=docker_network,
        local_image=local_image,
        allow_print_keys=None,
        keep_compose_prefix=None,
        keep_storage=None,
        keep_metrics=None,
        bind_address=bind_address,
        explicitly_provided=explicitly_provided,
    )


@translate_to_install_error
def _infra_install_apply(config: InfraInstallConfig) -> None:
    """Infra's apply-phase: write .env/compose and pull the image. No prompts - config already resolved.

    Ensures `config.directory` exists (an idempotent no-op on a fresh install, where `_infra_config()`'s
    own `inspect()` call already created it) so a self-healing repair - which reapplies the config
    persisted by `_infra_config()` instead of re-resolving it - can recreate a directory that was
    deleted out from under an already-completed install, without going through `inspect()`/`resolve()`
    again (which would read a now-missing `.env` and mint a fresh `DF_INFRA_API_KEY`, silently
    invalidating server's already-resolved config).
    """
    ensure_directory(config.directory, force_install=True)
    infra_apply(config, will_auto_start=True)


@translate_to_install_error
def _infra_start(directory: Path) -> None:
    """Start infra. Mirrors infra's own install()'s start_infra error handling."""
    try:
        start_infra(directory)
    except (DockerNetworkError, typer.Exit) as exc:
        reason = str(exc) if isinstance(exc, DockerNetworkError) else "see console output above for details."
        echo.error(f"Failed to start infra: {reason}")
        reraise_if_debug(exc)


def _infra_localhost_url(directory: Path) -> str:
    """The CLI process runs outside Docker, so post-start actions must reach infra via the host."""
    env_file = directory / ".env"
    port = env_get(env_file, "DF_INFRA_PORT", should_raise=False) or DF_INFRA_PORT
    return local_url(port, env_get(env_file, "DF_INFRA_BIND_ADDRESS", should_raise=False))


def _infra_post_start_action(action: PostStartAction, directory: Path, quiet: bool) -> None:
    """Run one of the resolved infra template's post-start actions (e.g. a service or model install).

    Args:
        action: The post-start action to run, exactly as declared by the resolved infra template
            (see `install()`'s `infra_post_start_actions`).
        directory: Infra's install directory, used to inject a localhost server URL - the CLI
            process runs outside Docker, so a post-start action must reach infra via localhost, not
            a docker-network hostname the template's own config might otherwise imply.
        quiet: Suppress the "Updated config/secrets" confirmation - passed as `resume`, since only
            a `--resume` run repeats this call (once per action, all against the exact same,
            already-confirmed connection) enough times for that confirmation to become noise; a
            fresh run only ever sees it once per call and it's still worth showing there.
    """
    infra_dispatch_post_start_action(
        {
            "function": action["function"],
            "kwargs": {**action["kwargs"], "server": _infra_localhost_url(directory), "quiet": quiet},
        }
    )


@translate_to_install_error
def _server_config(
    infra_config: InfraInstallConfig,
    name: str,
    email: str,
    password: str,
    force_install: bool,
    *,
    port: int,
    bind_address: str | None = None,
    image: str | None,
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
    nightshift_mode: str,
    nightshift_start: str,
    nightshift_stop: str,
    rabbitmq_url: str,
    rabbitmq_username: str,
    rabbitmq_password: str,
    otel_local: bool,
    template: str,
    explicitly_provided: Collection[str],
    skip_version_check: bool = False,
    checked_image: str | None = None,
) -> ServerInstallConfig:
    """Server's ask-phase: inspect() + resolve(), collecting every server-side prompt. No apply.

    Mirrors `deepfellow.server.utils.install.install()`'s own body for this phase, with the resolved
    `--template` (see `install()`'s own docstring for suite install's built-in-only restriction on
    it), and forwards the config-level flags (port, image, directory, MongoDB/FalkorDB, ...) `server
    install` itself accepts. Unlike before this function existed, the infra API key comes straight
    from infra's own already-resolved (not necessarily yet applied) config - not read back out of
    infra's `.env` after infra's apply-phase has run - which is what lets this run before
    `STEP_INFRA_INSTALL` rather than after it. See `_infra_config()` for why this is decorated.
    """
    # Always explicit: this key was just resolved for the infra installation this suite run is
    # about to perform, so it must never be silently outranked by a template's own
    # "infra_api_key" - unlike port/docker_network, this isn't conditional on a suite CLI flag
    # being passed, since suite is the one deciding it.
    explicitly_provided = set(explicitly_provided) | {"infra_api_key"}

    context = server_inspect(
        directory=directory,
        image=image,
        local_image=local_image,
        force_install=force_install,
        template=template,
        admin_name=name,
        admin_email=email,
        admin_password=password,
        skip_version_check=skip_version_check,
        checked_image=checked_image,
    )
    return server_resolve(
        context,
        port=port,
        otel_url=None,
        otel_local=otel_local,
        infra_url=DF_INFRA_URL,
        infra_api_key=infra_config.api_key,
        docker_network=docker_network,
        mongodb_url=DF_MONGO_URL,
        mongodb_port=mongodb_port,
        mongodb_database_name=DF_MONGO_DB,
        mongodb_username=mongodb_username,
        mongodb_password=mongodb_password,
        vectordb_active=bool(DEFAULT_VECTOR_DATABASE["provider"]["active"]),
        vectordb_type=VectorDBTypeChoice(DEFAULT_VECTOR_DATABASE_TYPE),
        vectordb_url=DEFAULT_VECTOR_DATABASE["provider"]["url"],
        vectordb_database_name=MILVUS_DATABASE["provider"]["db"],
        vectordb_username="",
        vectordb_password="",
        embedding_model=DEFAULT_VECTOR_DATABASE["embedding"]["model"],
        embedding_size=DEFAULT_VECTOR_DATABASE["embedding"]["size"],
        embedding_sparse=False,
        falkordb_active=falkordb_active,
        falkordb_url=falkordb_url,
        falkordb_username=falkordb_username,
        falkordb_password=falkordb_password,
        nightshift_mode=nightshift_mode,
        nightshift_start=nightshift_start,
        nightshift_stop=nightshift_stop,
        rabbitmq_url=rabbitmq_url,
        rabbitmq_username=rabbitmq_username,
        rabbitmq_password=rabbitmq_password,
        local_image=local_image,
        dev=False,
        bind_address=bind_address,
        explicitly_provided=explicitly_provided,
    )


@translate_to_install_error
def _server_install_apply(config: ServerInstallConfig) -> None:
    """Server's apply-phase: write .env/compose and pull the image. No prompts - config already resolved.

    Ensures `config.directory` exists (an idempotent no-op on a fresh install, where
    `_server_config()`'s own `inspect()` call already created it), so a self-healed server
    directory is recreated without going through `inspect()`/`resolve()` again - which would
    re-prompt for every server setting.
    """
    ensure_directory(config.directory, force_install=True)
    server_apply(config, will_auto_start=True)


@translate_to_install_error
def _server_start(directory: Path) -> None:
    """Start server. Mirrors server's own install()'s start_server error handling."""
    try:
        start_server(directory)
    except (DockerNetworkError, typer.Exit) as exc:
        reason = str(exc) if isinstance(exc, DockerNetworkError) else "see console output above for details."
        echo.error(f"Failed to start server: {reason}")
        reraise_if_debug(exc)


def _server_post_start_action(
    action: PostStartAction, directory: Path, name: str, email: str, password: str, admin_overridden: bool
) -> None:
    """Run one of the resolved server template's post-start actions (e.g. creating the admin account).

    server.create_admin is special-cased to use the exact admin credentials suite install already
    resolved up front - rather than the template's own (typically None) name/email/password kwargs,
    which server install would otherwise prompt for - and the actually-installed server directory,
    rather than whatever the template guessed (mirrors `server.utils.install._run_post_start_actions`'s
    own override of both). This is what lets create-admin and the later STEP_SERVER_LOGIN log into the
    exact same account. Any other resolved action type is dispatched unmodified through server's own
    dispatch_post_start_action(), exactly as `server install --template` itself would run it - so a
    future server template's post-start action is never silently dropped by suite install.

    Args:
        action: The post-start action to run, exactly as declared by the resolved server template
            (see `install()`'s `server_post_start_actions`).
        directory: Server's install directory, forced onto a server.create_admin action in place of
            whatever the template guessed.
        name: Resolved admin name, forced onto a server.create_admin action.
        email: Resolved admin email, forced onto a server.create_admin action.
        password: Resolved admin password, forced onto a server.create_admin action.
        admin_overridden: Whether name/email/password were actively supplied on *this* invocation -
            via an explicit --admin-*/env var, or by being interactively prompted for - as opposed
            to purely a prior run's persisted value being reused untouched. When True and an admin
            for `email` already exists, that supplied value was silently ignored (create_admin_util()
            only ever creates or no-ops, it never updates an existing account) - surfaced here as a
            warning instead of leaving the user to assume it applied. Ignored for any action other
            than server.create_admin.
    """
    if action["function"] != "server.create_admin":
        server_dispatch_post_start_action(action)
        return

    created = create_admin_util(directory=directory, name=name, email=email, password=password)
    if not created and admin_overridden:
        echo.warning(
            f"The admin name/email/password just given were ignored: an admin account for {email} "
            "already exists for this installation; its name/email/password are unchanged."
        )


def _run_server_post_start_actions(
    run_step: Callable[..., Any],
    server_post_start_actions: list[PostStartAction],
    server_directory: Path,
    name: str,
    email: str,
    password: str,
    admin_overridden: bool,
) -> None:
    """Run one step per entry of the resolved server template's post_start_actions, in order.

    Extracted out of install() purely to keep its own cyclomatic complexity down - same rationale
    as `_infra_config_on_skip()`. Each step is `always_run=True`: every resolved server post-start
    action is proven idempotent (server.create_admin's existing-admin response is a clean no-op -
    see server/utils/users.py) and none of them require the server container to be up/detected via
    docker ps - server.create_admin runs its own `docker compose run --rm server ...`.
    """
    for index, action in enumerate(server_post_start_actions):
        run_step(
            _server_post_start_action_step_id(index),
            # partial() binds `action` at each iteration, not at call time - unlike a bare lambda
            # closing over the loop variable, which would have every step run against whatever
            # `action` happened to be last (the classic late-binding closure pitfall) - same as the
            # matching infra post-start-action loop in install().
            partial(_server_post_start_action, action, server_directory, name, email, password, admin_overridden),
            always_run=True,
        )


@dataclass(frozen=True)
class _WorkspaceApply:
    """What Workspace is installed with besides the answers of `_workspace_config()`.

    Saved in `SuiteInstallState.workspace_apply`, so `--resume` installs the Workspace its address was given for.

    Attributes:
        directory: Workspace install directory.
        port: Published Workspace port; `None` keeps the default.
        image: Workspace docker image; `None` keeps the default.
        local_image: Use a locally built Workspace image, which is never pulled.
        bind_address: Host address to publish the Workspace port on; `None` keeps the default.
        small_model: Model Workspace uses for background tasks.
        docker_network: Docker network shared with Server, the one Server was installed on.
        overrides: Further Workspace .env values given explicitly (external MongoDB/Redis, SMTP, MCP token);
            those left `None` are ignored.
    """

    directory: str
    port: int | None
    image: str | None
    local_image: bool
    bind_address: str | None
    small_model: str
    docker_network: str
    overrides: dict[str, str | None]


def _workspace_apply_from_dict(data: dict[str, Any]) -> _WorkspaceApply:
    """Rebuild what Workspace is installed with from the saved state.

    Raises:
        InstallError: If `data` isn't what `asdict()` of a `_WorkspaceApply` gives.
    """
    try:
        return _WorkspaceApply(**data)
    except TypeError as exc:
        raise InstallError(
            "Suite install state file's saved Workspace settings are invalid or corrupted; remove "
            f"{DF_SUITE_INSTALL_STATE_FILE} and start over."
        ) from exc


def _validate_workspace_apply(
    apply: _WorkspaceApply, address: Mapping[str, str], granted_models: Collection[str]
) -> None:
    """Refuse Workspace settings that `workspace install` would only refuse at the very end of the suite install.

    Args:
        apply: What Workspace is going to be installed with.
        address: Answers of `_workspace_config()`.
        granted_models: Models the Workspace project is granted.

    Raises:
        InstallError: When the small model isn't granted, the database name comes without an external MongoDB, or
            the SMTP settings are only partly given.
    """
    given = {key: value for key, value in apply.overrides.items() if value is not None}
    if apply.small_model not in granted_models:
        raise InstallError(
            f"--workspace-small-model {apply.small_model} is not one of the models granted to the workspace project: "
            f"{', '.join(sorted(granted_models))}."
        )
    if given.get("MONGO_DB_NAME") and not given.get("MONGO_DB_URL"):
        raise InstallError(
            "--workspace-mongodb-database-name applies to an external MongoDB only; "
            "give --workspace-mongodb-url as well."
        )
    # A directory left by an earlier install may already hold part of a group, which a flag completes.
    existing = read_existing_env(Path(apply.directory))
    if problems := incomplete_groups({**existing, **address, **given}):
        raise InstallError("; ".join(problems) + ".")


def _workspace_install(
    workspace: Workspace, server_url: str, address: Mapping[str, str], apply: _WorkspaceApply
) -> None:
    """Install DeepFellow Workspace against the Server just installed, using the workspace's project API key.

    The initial Workspace admin is a separate account from the Server admin: its credentials are part of `address`
    (see `_workspace_config()`). Notifications from Server are set up only when the address is a public https
    address (see `configure_webhook()`). Workspace always runs its own MongoDB and Redis in Docker unless an
    external one is given in `apply.overrides`; no questions about them (or SMTP) are asked, and any external ones
    left from an earlier Workspace install are forgotten unless given again. `workspace env set` changes them
    afterwards.

    Args:
        workspace: The organization, project and API key created for Workspace.
        server_url: DeepFellow Server address as this host reaches it.
        address: Answers of `_workspace_config()` (the address Workspace is opened at, trusted origins, the initial
            admin account), so nothing is asked here. A directory left by an earlier attempt is reinstalled over
            without asking, since the question was asked, and answered, there.
        apply: The remaining settings Workspace is installed with, as saved by the first run.

    Raises:
        InstallError: If Workspace can't be installed.
    """
    passed: dict[str, str | None] = {
        "DF_SERVER_URL": _SERVER_URL_IN_DOCKER_NETWORK,
        "DF_SERVER_API_KEY": workspace.api_key.value,
        "DF_SERVER_ORGANIZATION_ID": workspace.organization.id,
        "DF_SERVER_PROJECT_ID": workspace.project.id,
        "SMALL_MODEL": apply.small_model,
        **address,
    }
    given = {key: value for key, value in apply.overrides.items() if value is not None}
    passed.update(given)
    try:
        install_workspace(
            passed,
            directory=Path(apply.directory),
            image=apply.image,
            local_image=apply.local_image,
            port=apply.port,
            bind_address=apply.bind_address,
            docker_network=apply.docker_network,
            force_install=True,
            # The Mongo and Redis bundled in Workspace's own Docker stack, even over an earlier Workspace
            # install that was pointed at external ones - unless an external one is given now.
            reset=tuple(key for key in _WORKSPACE_LOCAL_SERVICE_KEYS if key not in given),
            ask_optional_settings=False,
            cli_server_url=server_url,
            # The state file is deleted only by a suite install that succeeds; `workspace install` would leave it.
            retry_hint="run 'suite install --resume'",
        )
    except (OSError, ValueError) as exc:
        raise InstallError(str(exc)) from exc


def _workspace_config(
    apply: _WorkspaceApply,
    public_url: str | None,
    trusted_proxy: bool | None,
    trusted_origins: str | None,
    force_install: bool,
    admin_name: str | None,
    admin_email: str | None,
    admin_password: str | None,
    server_admin_password: str,
    granted_models: Collection[str],
) -> dict[str, str]:
    """Ask every question Workspace's installation has, before anything is installed.

    That is whether to reinstall over an existing Workspace directory, the initial Workspace admin account (its
    password must differ from the Server admin's), the address Workspace is opened at and, for an https one, the other
    trusted origins. `_workspace_install()` is handed the answers. The other Workspace settings are checked here too,
    so a mistake in them doesn't surface only after everything else has been installed.

    Args:
        apply: The remaining Workspace settings (directory, port, Docker network, ...).
        public_url: Address given explicitly; `None` asks (or takes the default when not asking).
        trusted_proxy: Trust the reverse proxy in front of Workspace; `None` enables it for an https address.
        trusted_origins: Other trusted origins, comma-separated; `None` asks for them with an https address.
        force_install: Skip the question about overwriting an existing Workspace directory.
        admin_name: Initial Workspace admin's name; `None` asks.
        admin_email: Initial Workspace admin's e-mail; `None` asks.
        admin_password: Initial Workspace admin's password; `None` asks.
        server_admin_password: Password of the Server admin, which the Workspace admin must not reuse.
        granted_models: Models the Workspace project is granted.

    Returns:
        The Workspace .env values answered, keyed by their .env name.

    Raises:
        typer.Exit: When the user declines to reinstall over an existing Workspace directory.
        InstallError: When the address is not valid, or the admin account is missing (`--non-interactive`) or
            has the Server admin's password, or `apply` is not valid - see `_validate_workspace_apply()`.
    """
    directory = Path(apply.directory)
    existing = read_existing_env(directory)
    _, resolved_port, _, _ = resolve_stack_settings(existing, None, apply.port, None, apply.docker_network)
    if directory.is_dir() and not force_install and not confirm_overwrite(directory):
        raise typer.Exit(1)
    admin = _resolve_workspace_admin(admin_name, admin_email, admin_password, server_admin_password)
    given = {
        PUBLIC_URL_KEY: public_url,
        TRUSTED_PROXY_KEY: None if trusted_proxy is None else str(trusted_proxy).lower(),
        TRUSTED_ORIGINS_KEY: trusted_origins,
    }
    passed: dict[str, str | None] = {key: value for key, value in given.items() if value is not None}
    address = resolve_public_url(passed, existing, resolved_port)
    if warning := insecure_context_warning(address):
        echo.warning(warning)
    apply_https_settings(passed, existing, address)
    config = {
        **{key: value or "" for key, value in passed.items() if key != PUBLIC_URL_KEY},
        PUBLIC_URL_KEY: address,
        **admin,
    }
    _validate_workspace_apply(apply, config, granted_models)
    return config


def _workspace_overrides(
    mongodb_url: str | None, mongodb_database_name: str | None, redis_url: str | None, others: Mapping[str, str | None]
) -> dict[str, str | None]:
    """Collect the Workspace .env values that are only set when given: external Mongo/Redis, SMTP, MCP token."""
    return {
        "MONGO_DB_URL": mongodb_url,
        "MONGO_DB_NAME": mongodb_database_name,
        "REDIS_URL": redis_url,
        **others,
    }


def _save_workspace_config(install_state: SuiteInstallState, apply: _WorkspaceApply, config: dict[str, str]) -> None:
    """`on_success` for `STEP_WORKSPACE_CONFIG`: keep the answers together with the settings they were given for."""
    install_state.workspace_config = config
    install_state.workspace_apply = asdict(apply)


def _saved_workspace_apply(install_state: SuiteInstallState) -> _WorkspaceApply:
    """Return the Workspace settings the Workspace configuration step saved (it always does, run or skipped).

    Raises:
        InstallError: If the saved settings are missing or corrupted - see `_workspace_apply_from_dict()`.
    """
    return _workspace_apply_from_dict(install_state.workspace_apply or {})


def _different_password(value: str | None, server_password: str) -> str | None:
    """Validate a Workspace admin password, which must differ from the Server admin's (compared trimmed).

    Raises:
        typer.BadParameter: When `value` is not a valid password, or equals `server_password`.
    """
    valid = validate_password(value)
    if valid and valid.strip() == server_password.strip():
        raise typer.BadParameter("The Workspace admin must have a different password than the Server admin.")
    return valid


def _validate_workspace_admin_given(
    name: str | None, email: str | None, password: str | None, server_password: str
) -> None:
    """Refuse a Workspace admin that `--non-interactive` can't complete, or a password given equal to Server admin's.

    Raises:
        InstallError: When a value is missing and `--non-interactive` can't prompt, or the password given equals the
            Server admin's.
    """
    missing = [flag for flag, value in (("name", name), ("email", email), ("password", password)) if not value]
    if missing and not is_interactive():
        flags = ", ".join(f"--workspace-admin-{flag}" for flag in missing)
        raise InstallError(
            f"The Workspace admin is missing {', '.join(missing)}; --non-interactive can't ask. Pass {flags}."
        )
    if password:
        try:
            _different_password(password, server_password)
        except typer.BadParameter as exc:
            raise InstallError(exc.message) from exc


def _validate_workspace_admin_up_front(
    install_state: SuiteInstallState, name: str | None, email: str | None, password: str | None, server_password: str
) -> None:
    """Refuse a Workspace admin the install can't use, before anything is installed.

    See `_validate_workspace_admin_given()`. Otherwise only the Workspace configuration step refuses it, after the
    infra and server directories exist.
    """
    if STEP_WORKSPACE_CONFIG not in install_state.completed_steps:
        _validate_workspace_admin_given(name, email, password, server_password)


def _resolve_workspace_admin(
    name: str | None, email: str | None, password: str | None, server_password: str
) -> dict[str, str]:
    """Resolve the initial Workspace admin account, whose password must differ from Server admin's.

    The e-mail may be the Server admin's. Values not given are prompted for; a password given equal to the Server
    admin's fails, a prompted one is asked again. Passwords are compared trimmed, as Workspace trims them.

    Args:
        name: Workspace admin's name; `None` prompts.
        email: Workspace admin's e-mail; `None` prompts.
        password: Workspace admin's password; `None` prompts.
        server_password: Password of the Server admin.

    Returns:
        The `BOOTSTRAP_ADMIN_*` Workspace .env values.

    Raises:
        InstallError: When a value is missing and `--non-interactive` can't prompt, or password given
            equals the Server admin's.
    """
    _validate_workspace_admin_given(name, email, password, server_password)
    echo.info("The Workspace admin is a separate account from the Server admin and needs its own password.")
    name = name or echo.prompt_until_valid("Provide Workspace admin name", validate_truthy)
    email = email or echo.prompt_until_valid("Provide Workspace admin email", validate_email)
    if not password:
        echo.info(PASSWORD_REQUIREMENTS)
        password = echo.prompt_until_valid(
            "Provide Workspace admin password",
            partial(_different_password, server_password=server_password),
            password=True,
        )
    return {
        "BOOTSTRAP_ADMIN_NAME": str(name),
        "BOOTSTRAP_ADMIN_EMAIL": str(email),
        "BOOTSTRAP_ADMIN_PASSWORD": str(password),
    }


def _saved_workspace_config(install_state: SuiteInstallState) -> dict[str, str]:
    """Return the Workspace answers the Workspace configuration step saved, checked to be what it saves.

    Raises:
        InstallError: If they are missing, aren't a mapping of strings, or have no admin account.
    """
    saved = install_state.workspace_config
    if (
        not isinstance(saved, dict)
        or not all(isinstance(key, str) and isinstance(value, str) for key, value in saved.items())
        or not all(saved.get(key) for key in _WORKSPACE_ADMIN_KEYS)
    ):
        raise InstallError(
            "Suite install state file's saved Workspace answers are invalid or corrupted; remove "
            f"{DF_SUITE_INSTALL_STATE_FILE} and start over."
        )
    return saved


def _workspace_config_on_skip(
    install_state: SuiteInstallState,
    explicitly_provided: Collection[str],
    admin_password: str | None,
    server_admin_password: str,
) -> dict[str, str]:
    """`on_skip` for `STEP_WORKSPACE_CONFIG` - see `_infra_config_on_skip()`.

    The saved Workspace admin password is checked against the Server admin's again, since `--admin-password` may
    have changed on the resuming run; the password is then asked for (or taken from `--workspace-admin-password`)
    again, and saved.

    Args:
        install_state: This run's progress state, holding the persisted answers.
        explicitly_provided: Names of the options given on this invocation.
        admin_password: Initial Workspace admin's password given on this invocation; `None` asks.
        server_admin_password: Password of the Server admin, which the Workspace admin must not reuse.

    Returns:
        The persisted Workspace answers.

    Raises:
        InstallError: When the saved answers are invalid, or a new admin password can't be resolved - see
            `_saved_workspace_config()` and `_resolve_workspace_admin()`.
    """
    config = dict(_saved_workspace_config(install_state))
    ignored = _WORKSPACE_ADDRESS_FIELDS | _WORKSPACE_APPLY_FIELDS
    if config["BOOTSTRAP_ADMIN_PASSWORD"].strip() == server_admin_password.strip():
        echo.warning("The saved Workspace admin password is now the Server admin's; asking for another one.")
        config |= _resolve_workspace_admin(
            config["BOOTSTRAP_ADMIN_NAME"], config["BOOTSTRAP_ADMIN_EMAIL"], admin_password, server_admin_password
        )
        ignored = ignored - {"workspace_admin_password"}  # used just now
        install_state.workspace_config = config
        save_state(install_state)
    _warn_config_flags_ignored("workspace", explicitly_provided, ignored)
    return config


def _run_step(
    install_state: SuiteInstallState,
    steps: tuple[tuple[str, str], ...],
    step_id: str,
    func: Callable[[], Any],
    *,
    always_run: bool = False,
    is_done: Callable[[], bool] | None = None,
    on_success: Callable[[Any], None] | None = None,
    on_skip: Callable[[], Any] | None = None,
) -> Any:
    """Run one suite-install step, skipping it when already done and persisting progress on success.

    A step already marked complete in `install_state.completed_steps` is skipped outright unless
    `always_run` is set or `is_done` (when given) says otherwise - `is_done` lets a step reconfirm
    it's *still* true (e.g. a container is still running) rather than blindly trusting the persisted
    flag, so a step whose real-world effect quietly disappeared (a container removed, a directory
    deleted) gets redone instead of skipped and misdiagnosed as some other failure downstream.

    Args:
        install_state: This run's progress state.
        steps: This run's full, ordered (step id, display name) list - see `_build_steps()`. Passed
            in rather than read from a module constant, since it depends on the resolved
            `--template`'s post-start-action count.
        step_id: The step being run.
        func: The step's work.
        always_run: Run `func` even when already done (e.g. a proven-idempotent action that isn't
            cheaply live-checkable).
        is_done: Overrides the default "was it in completed_steps" check.
        on_success: Called with `func`'s return value on success.
        on_skip: Called instead of `func` when the step is skipped as already done.
    """
    index, display_name = _step_position(steps, step_id)
    total_steps = len(steps)

    def _guarded(step_func: Callable[[], Any]) -> Any:
        # Shared by both func() and on_skip() below - a skipped step's own on_skip callback (e.g.
        # reconstructing a Workspace from persisted state) can fail on bad data just as easily as
        # the step's real work can fail on a live error, and must surface the same way, not crash
        # with an unhandled traceback for merely taking the "already done" branch.
        try:
            return step_func()
        except InstallError as exc:
            echo.error(f"Step {index}/{total_steps} ({display_name}) failed: {exc}")
            raise typer.Exit(1) from exc
        except typer.Exit as exc:
            echo.error(f"Step {index}/{total_steps} ({display_name}) failed; see console output above for details.")
            raise typer.Exit(1) from exc

    was_previously_completed = step_id in install_state.completed_steps
    already_done = is_done() if is_done is not None else was_previously_completed
    if already_done and not always_run:
        echo.info(f"Step {index}/{total_steps}: {display_name}... already completed, skipping.")
        return _guarded(on_skip) if on_skip is not None else None

    if was_previously_completed and not already_done:
        echo.warning(
            f"Step {index}/{total_steps}: {display_name}... was marked complete previously, but is "
            "no longer detected as up; re-running."
        )
    else:
        echo.info(f"Step {index}/{total_steps}: {display_name}...")
    result = _guarded(func)

    if on_success is not None:
        on_success(result)
    if step_id not in install_state.completed_steps:
        install_state.completed_steps.append(step_id)
    save_state(install_state)
    return result


@translate_to_install_error
def install(
    admin_name: str | None = None,
    admin_email: str | None = None,
    admin_password: str | None = None,
    force_install: bool = False,
    resume: bool = False,
    template: str = "suite",
    infra_port: int = DF_INFRA_PORT,
    infra_bind_address: str | None = None,
    infra_image: str | None = None,
    infra_local_image: bool = False,
    infra_directory: Path = DF_INFRA_DIRECTORY,
    infra_docker_config: Path | None = None,
    infra_storage: Path = DF_INFRA_STORAGE_DIR,
    server_port: int = DF_SERVER_PORT,
    server_bind_address: str | None = None,
    server_image: str | None = None,
    server_local_image: bool = False,
    skip_version_check: bool = False,
    server_directory: Path = DF_SERVER_DIRECTORY,
    docker_network: str = DF_INFRA_DOCKER_NETWORK,
    mongodb_port: int = DF_MONGO_PORT,
    mongodb_username: str = "",
    mongodb_password: str = "",
    falkordb_active: bool = False,
    falkordb_url: str = DF_FALKORDB_URL,
    falkordb_username: str = "",
    falkordb_password: str = "",
    nightshift_mode: str = DEFAULT_NIGHTSHIFT_MODE,
    nightshift_start: str = "",
    nightshift_stop: str = "",
    rabbitmq_url: str = DF_RABBITMQ_URL,
    rabbitmq_username: str = "",
    rabbitmq_password: str = "",
    otel_local: bool = False,
    allow_rootful: bool = False,
    explicitly_provided: Collection[str] = frozenset(),
    workspace_directory: Path = DF_WORKSPACE_DIRECTORY,
    workspace_port: int | None = None,
    workspace_public_url: str | None = None,
    workspace_bind_address: str | None = None,
    workspace_image: str | None = None,
    workspace_local_image: bool = False,
    workspace_small_model: str = DF_WORKSPACE_SMALL_MODEL,
    workspace_mongodb_url: str | None = None,
    workspace_mongodb_database_name: str | None = None,
    workspace_redis_url: str | None = None,
    workspace_smtp_host: str | None = None,
    workspace_smtp_port: int | None = None,
    workspace_smtp_secure: bool | None = None,
    workspace_smtp_username: str | None = None,
    workspace_smtp_password: str | None = None,
    workspace_email_from_address: str | None = None,
    workspace_email_from_name: str | None = None,
    workspace_trusted_proxy: bool | None = None,
    workspace_trusted_origins: str | None = None,
    workspace_mcp_auth_token: str | None = None,
    workspace_admin_name: str | None = None,
    workspace_admin_email: str | None = None,
    workspace_admin_password: str | None = None,
) -> None:
    """Provision a complete DeepFellow workspace: Infra, Server, admin user, and a ready-to-use workspace.

    Runs a sequence of granular steps, in order: infra configuration, server configuration, infra
    install, infra start, one step per service/model the resolved `template` installs on infra (the
    "suite" template installs the Ollama service and 3 models), server install, server start,
    one step per post-start action the resolved `template` runs on server (the "suite" template
    creates the admin account), server login, workspace creation, grant model access and Workspace install. The three
    configuration steps resolve every infra-, server- and Workspace-side prompt (directory-overwrite decisions,
    DF_NAME, vector DB, MongoDB, FalkorDB, the Workspace address, ...) before any of the later, purely
    programmatic steps run - so a user answers every question once at the start instead of partway through a
    long-running install.

    `template` selects the built-in template forwarded to both infra's and server's own
    configuration/post-start-action resolution. Unlike `infra install`'s/`server install`'s own
    `--template`, only a name known to both `deepfellow.infra.utils.templates.BUILTIN_TEMPLATES` and
    `deepfellow.server.utils.templates.BUILTIN_TEMPLATES` is accepted - not a path to a custom
    template file - validated before any prompt or installation action (see `_validate_template()`).
    Once resolved, `template` is persisted; a later `--resume` (or a declined discard, which behaves
    identically) always reuses the persisted value instead of trusting this argument again - warning
    if it differs - so a `--resume` invocation that passes a different `--template`, or simply omits
    it and falls back to its own default, can never mix one template's infra/server configuration
    with another template's installed services/models.

    Progress is persisted to a state file after each step succeeds. If a step fails, re-running
    with `--resume` skips every already-completed step and continues from the first incomplete one,
    instead of requiring manual recovery through individual `infra`/`server` subcommands. Re-running
    without `--resume` over an unfinished previous run's state asks for confirmation before
    discarding it and starting fresh (skipped by `--yes`); declining continues the previous run
    instead, exactly as `--resume` would.

    Args:
        admin_name: Admin user's name. Falls back to a prior run's persisted value on `--resume`,
            then to an interactive prompt.
        admin_email: Admin user's email. Same fallback order as admin_name.
        admin_password: Admin user's password. Same fallback order as admin_name.
        force_install: Force a reinstall over an already-existing infra/server directories.
        resume: Continue a previous, incomplete `suite install` run instead of starting fresh.
        template: Built-in template name forwarded to both infra's and server's own configuration/
            post-start-action resolution. Only a name known to both commands' own `BUILTIN_TEMPLATES`
            is accepted - see `_validate_template()`. On `--resume` (or a declined discard), a
            template already persisted by the run being continued wins over this argument instead.
        infra_port: Published port to serve the DeepFellow Infra from.
        infra_bind_address: Host address to publish the Infra port on; `None` keeps a prior install's
            value, falling back to all interfaces.
        infra_image: DeepFellow Infra docker image.
        infra_local_image: Whether to use a locally built DeepFellow Infra docker image.
        infra_directory: Target directory for the DeepFellow Infra installation.
        infra_docker_config: Path to the docker config used to pull the infra image.
        infra_storage: Storage directory for the DeepFellow Infra services.
        server_port: Port to use to serve the DeepFellow Server from.
        server_bind_address: Host address to publish the Server port on; `None` keeps a prior install's
            value, falling back to all interfaces.
        server_image: DeepFellow Server docker image.
        server_local_image: Whether to use a locally built DeepFellow Server docker image.
        skip_version_check: Install infra and server images whose version can't be checked against the CLI, or
            isn't compatible.
        server_directory: Target directory for the DeepFellow Server installation.
        docker_network: The Docker network name shared by infra and server.
        mongodb_port: Host port to publish the locally-managed MongoDB on.
        mongodb_username: Username for the locally-managed MongoDB's authentication.
        mongodb_password: Password for the locally-managed MongoDB's authentication.
        falkordb_active: Whether to enable the Knowledge Graph (FalkorDB) instance.
        falkordb_url: The host:port for the FalkorDB instance.
        falkordb_username: Username for FalkorDB authentication.
        falkordb_password: Password for FalkorDB authentication.
        nightshift_mode: Nightshift worker operating mode ("always" or "shift"). Nightshift/
            RabbitMQ are mandatory infrastructure, unlike FalkorDB - there is no active/inactive
            choice, only this mode.
        nightshift_start: Hour Nightshift worker should start (HH:MM, host timezone), shift mode only.
        nightshift_stop: Hour Nightshift worker should stop (HH:MM, host timezone), shift mode only.
        rabbitmq_url: The host:port for the RabbitMQ instance.
        rabbitmq_username: Username for RabbitMQ authentication.
        rabbitmq_password: Password for RabbitMQ authentication.
        otel_local: Whether to install a local debug-only OpenTelemetry collector.
        allow_rootful: Whether a rootful Docker socket is acceptable without asking - it is still
            warned about. Checked on every run, `--resume` included, before any prompt. On a
            `--resume` past the infra configuration step, this check only gates the run: the socket
            persisted by the original run is the one infra mounts, not the one found here.
        explicitly_provided: The subset of suite install's own config-flag names whose CLI option
            was actually passed on the command line or via envvar (not merely equal to its own
            default). Two independent uses: (a) infra_port/server_port/docker_network are mapped
            here onto infra's and server's own "port"/"docker_network" `_MERGEABLE_FIELDS` keys for
            template-value merge precedence; (b) any of them landing in this set is what lets
            install() warn when it had no effect because its install step was already done and
            skipped (see `_warn_config_flags_ignored`).
        workspace_directory: Target directory for the DeepFellow Workspace installation.
        workspace_port: Published port to serve Workspace from; `None` keeps the Workspace default.
        workspace_public_url: Address Workspace is opened at. Only a public https address makes Server
            notify Workspace (file indexing); `None` asks (or defaults to localhost without asking).
        workspace_bind_address: Host address to publish the Workspace port on; `None` keeps the default.
        workspace_image: Workspace docker image; `None` keeps the default.
        workspace_local_image: Use a locally built Workspace image, which is never pulled.
        workspace_small_model: Model Workspace uses for background tasks.
        workspace_mongodb_url: External MongoDB for Workspace; `None` installs one with Workspace.
        workspace_mongodb_database_name: Database name in the external MongoDB.
        workspace_redis_url: External Redis for Workspace; `None` installs one with Workspace.
        workspace_smtp_host: Workspace SMTP host. This and the other `workspace_smtp_*` and
            `workspace_email_from_*` values are left unset when `None`.
        workspace_smtp_port: Workspace SMTP port.
        workspace_smtp_secure: Use TLS from the start of the Workspace SMTP connection.
        workspace_smtp_username: Workspace SMTP username.
        workspace_smtp_password: Workspace SMTP password.
        workspace_email_from_address: Workspace sender e-mail address.
        workspace_email_from_name: Workspace sender name.
        workspace_trusted_proxy: Trust X-Forwarded-For / X-Real-IP in Workspace; `None` enables it for an https
            public URL.
        workspace_trusted_origins: Other origins Workspace trusts besides its public URL, comma-separated.
        workspace_mcp_auth_token: Bearer token required on Workspace's /mcp endpoint.
        workspace_admin_name: Initial Workspace admin's name; asked when `None`. A separate account from
            the Server admin.
        workspace_admin_email: Initial Workspace admin's e-mail; asked when `None`. May be the same as `admin_email`.
        workspace_admin_password: Initial Workspace admin's password; asked when `None`. Must differ from
            `admin_password`.

    Raises:
        InstallError: If `template` isn't a built-in template name known to both infra and server,
            if Docker is missing/unusable or its socket can't be found, if the socket belongs to
            rootful Docker and the user declines to continue without `allow_rootful` (always the
            case with --non-interactive), if any step fails, or if --non-interactive is set and an
            admin name, email, or password is missing.
    """
    # Checked before anything else, including the Docker check below: a bad --template value is a
    # pure input-validation failure, unrelated to Docker/prompting, so it should fail fastest of all.
    _validate_template(template)
    # A pure, deterministic lookup for a built-in name (see _validate_template() above) - no Docker,
    # filesystem, or prompting involved, so safe to resolve fresh here, once, purely to have a step
    # count for the "N/TOTAL_STEPS done" confirmation message below, in case this run turns out to
    # be continuing an unfinished previous one. If it is, and that previous run persisted a
    # DIFFERENT template, `template`/`infra_post_start_actions`/`server_post_start_actions`/`steps`/
    # `total_steps` all get recomputed below, against the persisted template instead - see the
    # template-resolution block right after prior_state is settled.
    infra_post_start_actions = infra_resolve_template(template)["post_start_actions"]
    server_post_start_actions = server_resolve_template(template)["post_start_actions"]
    steps = _build_steps(infra_post_start_actions, server_post_start_actions)
    total_steps = len(steps)

    # Checked before any prompting: infra install's own inspect() checks this too, but only once
    # step 1 actually runs, which is after the admin-credential prompts below. Checking it here
    # avoids making the user answer those prompts just to hit an unrelated Docker failure right
    # after.
    assert_docker()
    # Same reasoning for the socket lookup and its rootful Docker warning/prompt: resolved here, once,
    # and handed to the infra configuration step, so declining it doesn't come after the admin prompts
    # and the warning isn't shown a second time by infra's own inspect().
    docker_socket = get_socket(allow_rootful=allow_rootful)

    prior_state = load_state()
    if resume:
        install_state = prior_state if prior_state is not None else SuiteInstallState()
    elif prior_state is not None:
        # A plain (non --resume) run over an unfinished previous run's state would otherwise
        # silently discard it - including, if the previous run got that far, a workspace API key
        # that can never be retrieved again once lost. Confirm before doing that (skippable with
        # --yes, for scripted/CI use); declining just continues the previous run instead, exactly
        # as --resume would, so the user isn't forced into a second invocation. --non-interactive
        # has no prompt to fall back on, so it takes echo.confirm()'s own default (discard and
        # start fresh) - matching "no --resume = fresh" as the documented, unconditional default
        # for every suite install invocation, interactive or not.
        completed = len(prior_state.completed_steps)
        key_warning = (
            " This includes a workspace API key, which can never be retrieved again once discarded."
            if prior_state.workspace is not None
            else ""
        )
        if echo.confirm(
            f"A previous incomplete suite install exists ({completed}/{total_steps} steps done)."
            f"{key_warning} Discard it and start fresh instead of continuing it?",
            default=True,
        ):
            install_state = SuiteInstallState()
            # Overwritten immediately, not lazily on the first step's own save_state() call below -
            # otherwise a crash before step 1 completes would leave the OLD run's progress (and
            # possibly a different admin) on disk, unrelated to this fresh attempt.
            save_state(install_state)
            echo.warning("Previous suite install state discarded; starting fresh.")
        else:
            echo.info("Continuing the previous install instead.")
            install_state = prior_state
            # This path behaves exactly as --resume would (see comment above) - resume itself is
            # only otherwise read as the `quiet` flag on the ollama service/model install calls
            # below, so without this, declining the discard prompt would still print the
            # "Updated .../config."/"Updated .../secrets." noise --resume exists to silence.
            resume = True
    else:
        install_state = SuiteInstallState()

    # See _resolve_effective_template()'s own docstring: a persisted template from a run being
    # resumed always wins over this invocation's own --template. Recomputing
    # infra_post_start_actions/server_post_start_actions/steps/total_steps below (already done once
    # above, purely for the confirmation message) is free - see that computation's own comment.
    template = _resolve_effective_template(install_state, template)
    infra_post_start_actions = infra_resolve_template(template)["post_start_actions"]
    server_post_start_actions = server_resolve_template(template)["post_start_actions"]
    steps = _build_steps(infra_post_start_actions, server_post_start_actions)
    total_steps = len(steps)

    # Both images are validated before the first prompt or write: infra's configuration step would
    # otherwise create its directory and ask its questions before server's image gets refused. A step
    # that already ran (`--resume`) was validated back then.
    # The result is handed on to each step's inspect(), so the registry is asked (and the
    # --skip-version-check warning shown) once per component.
    infra_checked_image: str | None = None
    server_checked_image: str | None = None
    if STEP_INFRA_CONFIG not in install_state.completed_steps:
        infra_checked_image = resolve_install_image(
            "Infra",
            DF_INFRA_IMAGE_HUB,
            infra_image,
            infra_local_image,
            skip_version_check,
            "--infra-local-image",
            "--infra-image",
        )
    if STEP_SERVER_CONFIG not in install_state.completed_steps:
        server_checked_image = resolve_install_image(
            "Server",
            DF_SERVER_IMAGE_HUB,
            server_image,
            server_local_image,
            skip_version_check,
            "--server-local-image",
            "--server-image",
        )

    print_vram_estimate(infra_post_start_actions)

    # A prior run's persisted admin (if any) is the fallback source, same shape --admin-*/env vars
    # override: this is what lets `--resume` skip re-prompting for name/email/password it already
    # collected, while an --admin-* flag passed on the resuming invocation still wins over it.
    effective = resolve_admin_kwargs(install_state.admin or {}, admin_name, admin_email, admin_password)
    validate_non_interactive_admin_values(effective, "suite install")
    _validate_workspace_admin_up_front(
        install_state,
        workspace_admin_name,
        workspace_admin_email,
        workspace_admin_password,
        effective["password"] or "",
    )
    # Whether THIS invocation supplied an admin value that wasn't just a passthrough of a prior
    # run's persisted one - either via an explicit --admin-*/env var, or (set further below) by
    # being prompted for it, which only happens when neither a flag nor persisted state had a
    # value to fall back on. _server_post_start_action() uses this to warn instead of silently
    # discarding an override that turns out to target an already-existing account.
    admin_overridden = bool(admin_name or admin_email or admin_password)

    # Resolved once, up front: create-admin and login must use the exact same credentials, so the
    # admin created during server install can actually log in during the login step (server install's
    # create_admin post-start action prompts internally but never returns what it prompted for).
    name = effective["name"]
    if not name:
        name = echo.prompt_until_valid("Provide admin name", validate_truthy)
        admin_overridden = True
    email = effective["email"]
    if not email:
        email = echo.prompt_until_valid("Provide admin email", validate_email)
        admin_overridden = True

    password = effective["password"]
    if not password:
        echo.info(PASSWORD_REQUIREMENTS)
        password = echo.prompt_until_valid("Provide admin password", validate_password, password=True)
        admin_overridden = True

    # Written immediately, not lazily on the first step's own save_state() call below: a step that
    # never succeeds (e.g. the user repeatedly declining infra install's own directory-exists
    # confirmation) would otherwise leave nothing at all on disk, forcing the user to retype the
    # same name/email/password on every single `--resume` attempt even though nothing about the
    # admin identity itself ever needed re-asking.
    install_state.admin = {"name": name, "email": email, "password": password}
    save_state(install_state)
    echo.warning(
        f"The admin passwords, and once resolved, the full infra/server/workspace installation configuration, "
        f"are being saved in plain text to {DF_SUITE_INSTALL_STATE_FILE}, so `--resume` can reuse "
        "them without re-prompting. It's removed automatically once this install fully succeeds - "
        "if you abandon this run, remove it yourself."
    )

    run_step = partial(_run_step, install_state, steps)

    infra_explicitly_provided = _map_explicitly_provided(explicitly_provided, _INFRA_EXPLICIT_KEYS)
    server_explicitly_provided = _map_explicitly_provided(explicitly_provided, _SERVER_EXPLICIT_KEYS)

    # Both ask-phase steps run before any apply-phase step, so every infra and server prompt fires
    # up front. Each is only ever run once: after it succeeds, `on_skip` reconstructs the same
    # resolved config from persisted state on every later run (fresh or --resume) instead of
    # re-resolving (re-prompting) - and, since this is also the only place an explicit --infra-*/
    # --server-*/--mongodb-*/etc. flag could have taken effect, warns if one was passed anyway (it
    # was silently ignored). A state file from before these two steps existed (no persisted
    # `infra_config`/`server_config`) simply isn't "previously completed" for them, so they run
    # (and prompt) once more here - a one-time fallback, not a special case to code for.
    infra_config: InfraInstallConfig = run_step(
        STEP_INFRA_CONFIG,
        lambda: _infra_config(
            force_install,
            port=infra_port,
            bind_address=infra_bind_address,
            image=infra_image,
            local_image=infra_local_image,
            directory=infra_directory,
            docker_config=infra_docker_config,
            storage=infra_storage,
            docker_network=docker_network,
            template=template,
            explicitly_provided=infra_explicitly_provided,
            allow_rootful=allow_rootful,
            docker_socket=docker_socket,
            skip_version_check=skip_version_check,
            checked_image=infra_checked_image,
        ),
        on_success=lambda cfg: setattr(install_state, "infra_config", _infra_config_to_dict(cfg)),
        on_skip=partial(_infra_config_on_skip, install_state, explicitly_provided),
    )
    server_config: ServerInstallConfig = run_step(
        STEP_SERVER_CONFIG,
        lambda: _server_config(
            infra_config,
            name,
            email,
            password,
            force_install,
            port=server_port,
            bind_address=server_bind_address,
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
            nightshift_mode=nightshift_mode,
            nightshift_start=nightshift_start,
            nightshift_stop=nightshift_stop,
            rabbitmq_url=rabbitmq_url,
            rabbitmq_username=rabbitmq_username,
            rabbitmq_password=rabbitmq_password,
            otel_local=otel_local,
            template=template,
            explicitly_provided=server_explicitly_provided,
            skip_version_check=skip_version_check,
            checked_image=server_checked_image,
        ),
        on_success=lambda cfg: setattr(install_state, "server_config", _server_config_to_dict(cfg)),
        on_skip=partial(_server_config_on_skip, install_state, explicitly_provided),
    )
    # Derived from the resolved post-start actions the install steps run, so the two can never drift apart; also
    # known up front, to check Workspace's small model against.
    granted_models = [
        action["kwargs"]["model_name"]
        for action in infra_post_start_actions
        if action["function"] == "infra.model.install"
        and action["kwargs"]["service_name"] != "custom"
        and action["kwargs"]["model_name"] not in _DOC_CHUNKER_ONLY_MODELS
    ]

    # Settled by infra/server (a network of an earlier install wins over the flag), so Workspace joins the network
    # Server is really on.
    workspace_apply = _WorkspaceApply(
        directory=str(workspace_directory.expanduser().resolve()),
        port=workspace_port,
        image=workspace_image,
        local_image=workspace_local_image,
        bind_address=workspace_bind_address,
        small_model=workspace_small_model,
        docker_network=server_config.docker_network,
        overrides=_workspace_overrides(
            workspace_mongodb_url,
            workspace_mongodb_database_name,
            workspace_redis_url,
            {
                "SMTP_HOST": workspace_smtp_host,
                "SMTP_PORT": None if workspace_smtp_port is None else str(workspace_smtp_port),
                "SMTP_SECURE": None if workspace_smtp_secure is None else str(workspace_smtp_secure).lower(),
                "SMTP_USERNAME": workspace_smtp_username,
                "SMTP_PASSWORD": workspace_smtp_password,
                "EMAIL_FROM_ADDRESS": workspace_email_from_address,
                "EMAIL_FROM_NAME": workspace_email_from_name,
                "MCP_AUTH_TOKEN": workspace_mcp_auth_token,
            },
        ),
    )
    # Workspace's own questions, asked now with the rest so none is left for the end of a long install.
    workspace_config: dict[str, str] = run_step(
        STEP_WORKSPACE_CONFIG,
        lambda: _workspace_config(
            workspace_apply,
            workspace_public_url,
            workspace_trusted_proxy,
            workspace_trusted_origins,
            force_install,
            workspace_admin_name,
            workspace_admin_email,
            workspace_admin_password,
            password,
            granted_models,
        ),
        on_success=partial(_save_workspace_config, install_state, workspace_apply),
        on_skip=partial(
            _workspace_config_on_skip, install_state, explicitly_provided, workspace_admin_password, password
        ),
    )
    # What the first run settled; `workspace_config` is only skipped once saved together with it.
    workspace_apply = _saved_workspace_apply(install_state)

    # True when a step already marked complete has since gone missing/incomplete on disk
    # (self-healing rerun). `_infra_install_apply()` itself needs no such flag - it always
    # recreates the directory via `ensure_directory(..., force_install=True)`, prompt-free,
    # reapplying the config already persisted above rather than re-resolving it, so
    # DF_INFRA_API_KEY never regenerates on a repair - server's already-resolved config (which
    # embeds that same key) is never silently invalidated by it. This flag's only remaining use is
    # forcing STEP_INFRA_START to redo below, since a freshly-reapplied .env needs the container
    # restarted to actually load it.
    infra_needs_repair = STEP_INFRA_INSTALL in install_state.completed_steps and not _install_directory_intact(
        infra_directory
    )
    run_step(
        STEP_INFRA_INSTALL,
        lambda: _infra_install_apply(infra_config),
        is_done=partial(_install_still_done, install_state, STEP_INFRA_INSTALL, infra_directory),
    )
    run_step(
        STEP_INFRA_START,
        lambda: _infra_start(infra_directory),
        is_done=lambda: (
            not infra_needs_repair and _start_still_done(install_state, STEP_INFRA_START, "infra", infra_directory)
        ),
    )
    # Always run: not cheaply live-checkable (would need an Infra API round-trip), but proven
    # idempotent - install() already treats "already installed" as a clean no-op. Same rationale
    # as STEP_SERVER_LOGIN below. One step per resolved post-start action, in order - the
    # "suite" template's 4 actions (ollama service + 3 models) are what made this section look
    # fixed before; a different `template`'s action list changes this loop's length accordingly.
    for index, action in enumerate(infra_post_start_actions):
        run_step(
            _infra_post_start_action_step_id(index),
            # partial() binds `action` at each iteration, not at call time - unlike a bare lambda
            # closing over the loop variable, which would have every step run against whatever
            # `action` happened to be last (the classic late-binding closure pitfall).
            partial(_infra_post_start_action, action, infra_directory, resume),
            always_run=True,
        )

    # Same as infra_needs_repair above, but purely about server's own directory integrity -
    # repairing infra no longer regenerates DF_INFRA_API_KEY, so it no longer forces a server
    # repair in turn. This flag's only remaining use is forcing STEP_SERVER_START to redo below.
    server_needs_repair = STEP_SERVER_INSTALL in install_state.completed_steps and not _install_directory_intact(
        server_directory
    )
    run_step(
        STEP_SERVER_INSTALL,
        lambda: _server_install_apply(server_config),
        is_done=partial(_install_still_done, install_state, STEP_SERVER_INSTALL, server_directory),
    )
    run_step(
        STEP_SERVER_START,
        lambda: _server_start(server_directory),
        is_done=lambda: (
            not server_needs_repair and _start_still_done(install_state, STEP_SERVER_START, "server", server_directory)
        ),
    )
    # One step per resolved server post-start action, in order - see
    # `_run_server_post_start_actions()`'s own docstring for the always_run rationale. Extracted
    # into its own function purely to keep install()'s own cyclomatic complexity down - same
    # rationale as `_infra_config_on_skip()`.
    _run_server_post_start_actions(
        run_step, server_post_start_actions, server_directory, name, email, password, admin_overridden
    )
    set_default_server_directory(server_directory, force=False)

    # Read back the port server install actually resolved - not server_port, which _resolve_port()
    # (deepfellow/server/utils/install.py) silently overrides with a prior install's own DF_SERVER_PORT
    # whenever "port" isn't in server_explicitly_provided, e.g. on a re-run against a directory that
    # already has a different port configured. The CLI process runs outside Docker, so this must be
    # a host address (localhost unless bound to a specific one), not a docker-network hostname. No
    # default= here: server install (which just succeeded) always writes DF_SERVER_PORT to this .env,
    # so a missing file/key means something is genuinely broken - env_get's own should_raise=True
    # default is the right behavior, not a case to silently paper over with the raw --server-port value.
    resolved_server_port = env_get(server_directory / ".env", "DF_SERVER_PORT")
    server_bind_address = env_get(server_directory / ".env", "DF_SERVER_BIND_ADDRESS", should_raise=False)
    server_url = local_url(str(resolved_server_port), server_bind_address)

    # Always run: cheap and idempotent, and its result (the token) is needed below - unlike the
    # other steps, skipping it on resume would lose that result rather than merely redo cheap work.

    token = run_step(
        STEP_SERVER_LOGIN,
        lambda: get_token_from_login(state.cli_secrets_file, server_url, email=email, password=password),
        always_run=True,
    )

    # Workspace creation generates a project API key that can never be retrieved again after the
    # fact (see suite-install-resume spec) - unlike every other step, it must never be silently
    # re-run just because its output wasn't reused; if it already succeeded, its persisted result
    # is the only source of truth for that key.
    workspace: Workspace = run_step(
        STEP_WORKSPACE_CREATION,
        lambda: create_workspace(
            server_url, token, WORKSPACE_ORGANIZATION_NAME, WORKSPACE_PROJECT_NAME, WORKSPACE_API_KEY_NAME
        ),
        is_done=lambda: (
            STEP_WORKSPACE_CREATION in install_state.completed_steps and install_state.workspace is not None
        ),
        on_success=lambda ws: setattr(install_state, "workspace", _workspace_to_dict(ws)),
        on_skip=lambda: _workspace_from_dict(install_state.workspace),  # type: ignore[arg-type]
    )

    # Always run: not cheaply live-checkable (would need a Server API round-trip), but proven
    # idempotent - update_project() is a plain "set the models field" call. Same rationale as
    # STEP_SERVER_LOGIN above. The granted model list is derived from the same resolved
    # infra_post_start_actions the install steps above just ran, not a separate hardcoded list, so
    # the two can never drift apart. Models of the "custom" service (e.g. doc_chunker) are skipped:
    # Server gates those by the project's custom_endpoints, never by its models list. So are the
    # models only Doc Chunker uses, which Server reaches through Doc Chunker, not through a project.
    run_step(
        STEP_GRANT_MODEL_ACCESS,
        lambda: update_project(
            server_url,
            token,
            workspace.organization.id,
            workspace.project.id,
            {"models": granted_models},
        ),
        always_run=True,
    )

    # Last, since Workspace needs the project's models granted above. Re-runs when its directory
    # is gone; its questions were asked by STEP_WORKSPACE_CONFIG, so rewriting over its own earlier,
    # interrupted attempt does not ask again (secrets are kept, like `workspace install --force-install`).
    run_step(
        STEP_WORKSPACE_INSTALL,
        lambda: _workspace_install(workspace, server_url, workspace_config, workspace_apply),
        is_done=partial(_install_still_done, install_state, STEP_WORKSPACE_INSTALL, Path(workspace_apply.directory)),
    )

    delete_state()
    echo.success("DeepFellow workspace installed successfully.")
    echo.info(str(workspace))
