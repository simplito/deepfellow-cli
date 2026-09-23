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
from dataclasses import asdict
from functools import partial
from pathlib import Path
from typing import Any

import typer

from deepfellow.common.defaults import (
    DEFAULT_VECTOR_DATABASE,
    DEFAULT_VECTOR_DATABASE_TYPE,
    DF_FALKORDB_URL,
    DF_INFRA_DIRECTORY,
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_IMAGE,
    DF_INFRA_NAME,
    DF_INFRA_PORT,
    DF_INFRA_STORAGE_DIR,
    DF_INFRA_URL,
    DF_MONGO_DB,
    DF_MONGO_PORT,
    DF_MONGO_URL,
    DF_SERVER_DIRECTORY,
    DF_SERVER_IMAGE,
    DF_SERVER_PORT,
    DF_SUITE_INSTALL_STATE_FILE,
    MILVUS_DATABASE,
    VectorDBTypeChoice,
)
from deepfellow.common.docker import is_service_running
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get
from deepfellow.common.exceptions import DockerNetworkError, InstallError, reraise_if_debug, translate_to_install_error
from deepfellow.common.install import (
    assert_docker,
    ensure_directory,
    resolve_admin_kwargs,
    validate_non_interactive_admin_values,
)
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
from deepfellow.server.utils.configure import FalkorDBConfig, OtelConfig
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

WORKSPACE_ORGANIZATION_NAME = "Workspace"
WORKSPACE_PROJECT_NAME = "Default"
WORKSPACE_API_KEY_NAME = "app"

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
    STEP_INFRA_START and STEP_SERVER_INSTALL, in order - the "workspace" template's 4 actions
    (ollama service + 3 models) are what made this section look fixed before. Likewise, one step per
    entry of the resolved server template's post_start_actions is inserted between STEP_SERVER_START
    and STEP_SERVER_LOGIN - the "workspace" template's single server.create_admin action is what made
    that section look fixed before. A different --template's action count changes either list's
    length accordingly, with no other code change needed. Computed once per run (see install()), not
    a module-level constant, since it depends on the resolved --template.
    """
    return (
        (STEP_INFRA_CONFIG, "infra configuration"),
        (STEP_SERVER_CONFIG, "server configuration"),
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
    )


# Suite-level config flag names relevant to each install step, used by _warn_config_flags_ignored()
# below - a subset of _EXPLICITLY_PROVIDED_FIELDS (deepfellow/suite/install.py). docker_network is
# in both, since it applies to both infra and server installs.
_INFRA_CONFIG_FIELDS = frozenset(
    {
        "infra_port",
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
    to `"workspace"`, simply omits - the one the original run configured infra/server against would
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
    image: str,
    local_image: bool,
    directory: Path,
    docker_config: Path | None,
    storage: Path,
    docker_network: str,
    template: str,
    explicitly_provided: Collection[str],
) -> InfraInstallConfig:
    """Infra's ask-phase: inspect() + resolve(), collecting every infra-side prompt. No apply.

    Mirrors `deepfellow.infra.utils.install.install()`'s own body for this phase, with the resolved
    `--template` (see `install()`'s own docstring for suite install's built-in-only restriction on
    it), and forwards the config-level flags (port, image, directory, ...) `infra install` itself
    accepts. Decorated the same as every other step function - `translate_to_install_error` now
    propagates a wrapped function's return value unchanged, so this ask-phase function's resolved
    config still reaches its caller, while `DockerSocketNotFoundError`/`OSError`/`typer.BadParameter`
    raised anywhere in `inspect()`/`resolve()` (e.g. from `get_socket()`, `ensure_directory()`) still
    get translated to a clean `InstallError` right here - exactly like `_infra_install_apply` -
    instead of only being caught much later by `install()`'s own decorator, bypassing `_run_step()`'s
    per-step "Step N/TOTAL (name) failed: ..." message.
    """
    context = infra_inspect(
        directory=directory,
        allow_rootful=False,
        force_install=force_install,
        image=image,
        local_image=local_image,
        template=template,
    )
    docker_config = docker_config or directory / "docker-config.json"
    return infra_resolve(
        context,
        port=port,
        image=image,
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
    """The CLI process runs outside Docker, so post-start actions must reach infra via localhost."""
    port = env_get(directory / ".env", "DF_INFRA_PORT", should_raise=False) or DF_INFRA_PORT
    return f"http://localhost:{port}"


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
    template: str,
    explicitly_provided: Collection[str],
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
    )
    return server_resolve(
        context,
        port=port,
        image=image,
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
        local_image=local_image,
        dev=False,
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
    template: str = "workspace",
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

    Runs a sequence of granular steps, in order: infra configuration, server configuration, infra
    install, infra start, one step per service/model the resolved `template` installs on infra (the
    "workspace" template installs the Ollama service and 3 models), server install, server start,
    one step per post-start action the resolved `template` runs on server (the "workspace" template
    creates the admin account), server login, workspace creation, and grant model access. The two
    configuration steps resolve every infra- and server-side prompt (directory-overwrite decisions,
    DF_NAME, vector DB, MongoDB, FalkorDB, ...) before any of the later, purely programmatic steps
    run - so a user answers every question once at the start instead of partway through a
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
        explicitly_provided: The subset of suite install's own config-flag names whose CLI option
            was actually passed on the command line or via envvar (not merely equal to its own
            default). Two independent uses: (a) infra_port/server_port/docker_network are mapped
            here onto infra's and server's own "port"/"docker_network" `_MERGEABLE_FIELDS` keys for
            template-value merge precedence; (b) any of them landing in this set is what lets
            install() warn when it had no effect because its install step was already done and
            skipped (see `_warn_config_flags_ignored`).

    Raises:
        InstallError: If `template` isn't a built-in template name known to both infra and server,
            if Docker is missing/unusable, if any step fails, or if --non-interactive is set and an
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
        if state.yes or echo.confirm(
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

    # A prior run's persisted admin (if any) is the fallback source, same shape --admin-*/env vars
    # override: this is what lets `--resume` skip re-prompting for name/email/password it already
    # collected, while an --admin-* flag passed on the resuming invocation still wins over it.
    effective = resolve_admin_kwargs(install_state.admin or {}, admin_name, admin_email, admin_password)
    validate_non_interactive_admin_values(effective, "suite install")
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
        f"The admin password, and once resolved, the full infra/server installation configuration, "
        f"are being saved in plain text to {DF_SUITE_INSTALL_STATE_FILE}, so `--resume` can reuse "
        "them without re-prompting. It's removed automatically once this install fully succeeds - "
        "if you abandon this run, remove it yourself."
    )

    run_step = partial(_run_step, install_state, steps)

    # The only suite-level flags whose CLI option was actually passed also participate in infra's
    # or server's own template-value merging (_MERGEABLE_FIELDS) - mapped here onto infra's and
    # server's own "port"/"docker_network" keys, per install()'s own docstring.
    infra_explicitly_provided = {"port"} if "infra_port" in explicitly_provided else set()
    if "docker_network" in explicitly_provided:
        infra_explicitly_provided.add("docker_network")

    server_explicitly_provided = {"port"} if "server_port" in explicitly_provided else set()
    if "docker_network" in explicitly_provided:
        server_explicitly_provided.add("docker_network")

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
            image=infra_image,
            local_image=infra_local_image,
            directory=infra_directory,
            docker_config=infra_docker_config,
            storage=infra_storage,
            docker_network=docker_network,
            template=template,
            explicitly_provided=infra_explicitly_provided,
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
            template=template,
            explicitly_provided=server_explicitly_provided,
        ),
        on_success=lambda cfg: setattr(install_state, "server_config", _server_config_to_dict(cfg)),
        on_skip=partial(_server_config_on_skip, install_state, explicitly_provided),
    )

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
    # "workspace" template's 4 actions (ollama service + 3 models) are what made this section look
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
    # localhost, not a docker-network hostname. No default= here: server install (which just
    # succeeded) always writes DF_SERVER_PORT to this .env, so a missing file/key means something
    # is genuinely broken - env_get's own should_raise=True default is the right behavior, not a
    # case to silently paper over with the raw --server-port value.
    resolved_server_port = env_get(server_directory / ".env", "DF_SERVER_PORT")
    server_url = f"http://localhost:{resolved_server_port}"

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
    # the two can never drift apart.
    granted_models = [
        action["kwargs"]["model_name"]
        for action in infra_post_start_actions
        if action["function"] == "infra.model.install"
    ]
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

    delete_state()
    echo.success("DeepFellow workspace installed successfully.")
    echo.info(str(workspace))
