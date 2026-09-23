# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from collections.abc import Callable
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
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
    DF_SUITE_INSTALL_STATE_FILE,
)
from deepfellow.common.exceptions import InstallError
from deepfellow.common.state import state
from deepfellow.common.templates import InstallTemplate, PostStartAction
from deepfellow.infra.utils.install import InstallConfig as InfraInstallConfig
from deepfellow.infra.utils.templates import BUILTIN_TEMPLATES as INFRA_BUILTIN_TEMPLATES
from deepfellow.server.organization.utils import Organization
from deepfellow.server.project.api_key.utils import ApiKey
from deepfellow.server.project.utils import Project
from deepfellow.server.utils.configure import FalkorDBConfig, OtelConfig
from deepfellow.server.utils.install import InstallConfig as ServerInstallConfig
from deepfellow.server.utils.templates import BUILTIN_TEMPLATES as SERVER_BUILTIN_TEMPLATES
from deepfellow.server.utils.workspace import Workspace
from deepfellow.suite.utils.install import (
    _build_steps,
    _infra_config_from_dict,
    _infra_config_to_dict,
    _install_directory_intact,
    _resolve_effective_template,
    _server_config_from_dict,
    _server_config_to_dict,
    _validate_template,
    _workspace_to_dict,
    install,
)
from deepfellow.suite.utils.state import SuiteInstallState

PLAINTEXT_WARNING = (
    "The admin password, and once resolved, the full infra/server installation configuration, "
    f"are being saved in plain text to {DF_SUITE_INSTALL_STATE_FILE}, so `--resume` can reuse "
    "them without re-prompting. It's removed automatically once this install fully succeeds - "
    "if you abandon this run, remove it yourself."
)

# The default "workspace" template's real, production-defined post-start actions - derived from
# production's own BUILTIN_TEMPLATES rather than retyped, so these constants can't silently drift
# from what install()'s own (unmocked, pure-for-a-built-in-name) infra_resolve_template("workspace")/
# server_resolve_template("workspace") calls actually resolve in every test below that doesn't
# override `template`.
_WORKSPACE_POST_START_ACTIONS: list[PostStartAction] = INFRA_BUILTIN_TEMPLATES["workspace"]["post_start_actions"]
_SERVER_WORKSPACE_POST_START_ACTIONS: list[PostStartAction] = SERVER_BUILTIN_TEMPLATES["workspace"][
    "post_start_actions"
]
# Kept as `STEPS`/`TOTAL_STEPS` (test-local, not imported from production - see _build_steps() -
# these no longer exist as production module constants since the step list is template-dependent)
# so every existing STEPS/TOTAL_STEPS usage below needs no further change.
STEPS = _build_steps(_WORKSPACE_POST_START_ACTIONS, _SERVER_WORKSPACE_POST_START_ACTIONS)
TOTAL_STEPS = len(STEPS)


def _infra_install_apply_call() -> mock._Call:
    """`_infra_install_apply()` is always called with whatever `_infra_config`/`_infra_config_from_dict`
    resolved - both are pinned to `mock.sentinel.infra_config` by `_patch_all_steps`, regardless of
    whether the config step ran fresh or was skipped-and-reconstructed this run."""
    return mock.call(mock.sentinel.infra_config)


def _server_install_apply_call() -> mock._Call:
    """See `_infra_install_apply_call()` - server's counterpart, pinned to `mock.sentinel.server_config`."""
    return mock.call(mock.sentinel.server_config)


def _make_infra_config(**overrides: object) -> InfraInstallConfig:
    """A real InfraInstallConfig, since `_infra_config_to_dict()`/`_infra_config_from_dict()` call
    `dataclasses.asdict()`/construct the dataclass directly - a plain Mock() won't do."""
    base: dict[str, object] = {
        "directory": DF_INFRA_DIRECTORY,
        "docker_socket": "/var/run/docker.sock",
        "df_name": "deepfellow",
        "infra_url": "http://localhost:8085",
        "infra_port": DF_INFRA_PORT,
        "df_infra_image": DF_INFRA_IMAGE,
        "docker_network": DF_INFRA_DOCKER_NETWORK,
        "docker_config": DF_INFRA_DIRECTORY / "docker-config.json",
        "admin_api_key": "admin-api-key",
        "api_key": "infra-api-key",
        "mesh_key": "mesh-key",
        "compose_prefix": "dfabc123_",
        "storage_dir": DF_INFRA_STORAGE_DIR,
        "metrics_username": "metrics-user",
        "metrics_password": "metrics-pass",
        "hugging_face_token": None,
        "civitai_token": None,
        "local_image": False,
        "print_keys": False,
        "df_connect_to_mesh_url": None,
        "df_connect_to_mesh_key": None,
    }
    base.update(overrides)
    return InfraInstallConfig(**base)  # type: ignore[arg-type]


def _make_server_config(**overrides: object) -> ServerInstallConfig:
    """A real ServerInstallConfig - see `_make_infra_config()`."""
    base: dict[str, object] = {
        "directory": DF_SERVER_DIRECTORY,
        "port": DF_SERVER_PORT,
        "image": DF_SERVER_IMAGE,
        "docker_network": DF_INFRA_DOCKER_NETWORK,
        "log_level": "INFO",
        "plugins_setup": "{}",
        "metrics_username": "metrics-user",
        "metrics_password": "metrics-pass",
        "mongo_env": {},
        "custom_mongo_db_server": False,
        "infra_env": {},
        "vectordb_envs": {},
        "is_vectordb_active": False,
        "is_custom_vector_db_server": False,
        "vectordb_type": "milvus",
        "otel": OtelConfig(envs={}, docker_compose={}),
        "falkordb": FalkorDBConfig(envs={}, docker_compose={}),
        "local_image": False,
        "dev": False,
    }
    base.update(overrides)
    return ServerInstallConfig(**base)  # type: ignore[arg-type]


def _make_workspace(organization_id: str = "org-1", project_id: str = "project-1") -> Workspace:
    """A real Workspace, since `_workspace_to_dict()` calls `dataclasses.asdict()` on its parts -
    a plain Mock() isn't a dataclass instance and asdict() would raise on it."""
    return Workspace(
        organization=Organization(id=organization_id, created_at=0.0, name="Workspace", owner_id="owner-1"),
        project=Project(
            name="Default",
            id=project_id,
            status="active",
            models=[],
            custom_endpoints=[],
            mcp_prefixes=[],
            created_at=0.0,
        ),
        api_key=ApiKey(
            id="key-1",
            object="organization.project.api_key",
            name="app",
            redacted_value="sk-...",
            created_at=0.0,
            last_used_at=0.0,
            value="secret-key",
        ),
    )


def _patch_all_steps(func: Callable[..., None]) -> Callable[..., None]:
    """Patch every granular step function plus load/save/delete_state - the default "everything
    succeeds" scaffolding most tests build on.

    mock.patch decorators apply bottom-up, and the resulting mocks are passed to the test function
    in that same bottom-to-top order - so this list must be ordered to match each test's parameter
    list exactly (first entry here = first parameter after `self`-less signature). `is_service_running`
    and `_install_directory_intact` default to `return_value=True` ("still there") so every test not
    specifically exercising the live-state fix keeps today's "skip a step already in completed_steps"
    behavior unchanged. `_infra_config`/`_infra_config_from_dict` both default to returning the same
    `mock.sentinel.infra_config` (and the server pair to `mock.sentinel.server_config`) so a test
    doesn't need to care whether the config step ran fresh or was skipped-and-reconstructed this run -
    either way, `_infra_install_apply`/`_server_install_apply` see the same, predictable value. The
    `_to_dict` pair defaults to an empty dict, since round-tripping through them isn't what these
    integration-level tests are checking (see the dedicated `_infra_config_to_dict`/`_from_dict`
    tests for that). `env_get` is appended last purely so every existing signature only needs one
    new trailing parameter, since install() calls it exactly once itself (to resolve the
    actually-configured DF_SERVER_PORT) - independent of whichever step functions a test overrides.
    """
    # Explicit statements, not a loop: parameter order must match this exact wrap order (first
    # wrapped = innermost decorator = first parameter), and a loop over a reordered tuple is an
    # easy way to silently break that pairing.
    func = mock.patch("deepfellow.suite.utils.install._server_config_to_dict", return_value={})(func)
    func = mock.patch(
        "deepfellow.suite.utils.install._server_config_from_dict", return_value=mock.sentinel.server_config
    )(func)
    func = mock.patch("deepfellow.suite.utils.install._server_config", return_value=mock.sentinel.server_config)(func)
    func = mock.patch("deepfellow.suite.utils.install._infra_config_to_dict", return_value={})(func)
    func = mock.patch(
        "deepfellow.suite.utils.install._infra_config_from_dict", return_value=mock.sentinel.infra_config
    )(func)
    func = mock.patch("deepfellow.suite.utils.install._infra_config", return_value=mock.sentinel.infra_config)(func)
    func = mock.patch("deepfellow.suite.utils.install._install_directory_intact", return_value=True)(func)
    func = mock.patch("deepfellow.suite.utils.install.is_service_running", return_value=True)(func)
    func = mock.patch("deepfellow.suite.utils.install.assert_docker")(func)
    func = mock.patch("deepfellow.suite.utils.install.load_state")(func)
    func = mock.patch("deepfellow.suite.utils.install.save_state")(func)
    func = mock.patch("deepfellow.suite.utils.install.delete_state")(func)
    func = mock.patch("deepfellow.suite.utils.install.update_project")(func)
    func = mock.patch("deepfellow.suite.utils.install.create_workspace")(func)
    func = mock.patch("deepfellow.suite.utils.install.get_token_from_login")(func)
    func = mock.patch("deepfellow.suite.utils.install.set_default_server_directory")(func)
    func = mock.patch("deepfellow.suite.utils.install._server_post_start_action")(func)
    func = mock.patch("deepfellow.suite.utils.install._server_start")(func)
    func = mock.patch("deepfellow.suite.utils.install._server_install_apply")(func)
    func = mock.patch("deepfellow.suite.utils.install._infra_post_start_action")(func)
    func = mock.patch("deepfellow.suite.utils.install._infra_start")(func)
    func = mock.patch("deepfellow.suite.utils.install._infra_install_apply")(func)
    func = mock.patch("deepfellow.suite.utils.install.echo")(func)
    return mock.patch("deepfellow.suite.utils.install.env_get")(func)


@_patch_all_steps
def test_install_success_calls_all_steps_in_order(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    workspace = _make_workspace()
    mock_create_workspace.return_value = workspace

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_infra_config.call_count == 1
    assert mock_infra_config.call_args == mock.call(
        False,
        port=DF_INFRA_PORT,
        image=DF_INFRA_IMAGE,
        local_image=False,
        directory=DF_INFRA_DIRECTORY,
        docker_config=None,
        storage=DF_INFRA_STORAGE_DIR,
        docker_network=DF_INFRA_DOCKER_NETWORK,
        template="workspace",
        explicitly_provided=set(),
    )
    assert mock_server_config.call_count == 1
    assert mock_server_config.call_args.args[0] == mock.sentinel.infra_config
    assert mock_infra_install_apply.call_count == 1
    assert mock_infra_install_apply.call_args == _infra_install_apply_call()
    assert mock_infra_start.call_count == 1
    assert mock_infra_post_start_action.call_count == 4
    # Fresh (non --resume) run: "Updated config/secrets" stays visible - only --resume quiets it.
    assert mock_infra_post_start_action.call_args_list == [
        mock.call(action, DF_INFRA_DIRECTORY, False) for action in _WORKSPACE_POST_START_ACTIONS
    ]
    assert mock_server_install_apply.call_count == 1
    assert mock_server_install_apply.call_args == _server_install_apply_call()
    assert mock_server_start.call_count == 1
    assert mock_server_post_start_action.call_count == 1
    assert mock_set_default_server_directory.call_count == 1
    assert mock_set_default_server_directory.call_args == mock.call(DF_SERVER_DIRECTORY, force=False)
    assert mock_get_token_from_login.call_count == 1
    assert mock_get_token_from_login.call_args.kwargs["email"] == "admin@example.com"
    assert mock_get_token_from_login.call_args.kwargs["password"] == "Sup3r$ecret!"
    assert mock_create_workspace.call_count == 1
    assert mock_create_workspace.call_args.args[2:] == ("Workspace", "Default", "app")
    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args.args[2:] == (
        workspace.organization.id,
        workspace.project.id,
        {"models": ["gemma4:e4b", "mxbai-embed-large", "qwen3.5:4b"]},
    )
    # +1: admin credentials are written immediately once resolved, before any step runs.
    assert mock_save_state.call_count == TOTAL_STEPS + 1
    assert mock_save_state.call_args.args[0].completed_steps == [step_id for step_id, _ in STEPS]
    assert mock_delete_state.call_count == 1


@_patch_all_steps
def test_install_config_steps_run_before_any_apply_step(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """The core DFCLI-81/DFCLI-91 guarantee: both config (ask) steps complete before either apply
    action (infra or server) runs - not just before their OWN apply, but before either one's."""
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()
    call_order: list[str] = []
    for name, m in (
        ("infra_config", mock_infra_config),
        ("server_config", mock_server_config),
        ("infra_install_apply", mock_infra_install_apply),
        ("server_install_apply", mock_server_install_apply),
    ):
        m.side_effect = lambda *a, _name=name, **kw: call_order.append(_name)

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert call_order.index("infra_config") < call_order.index("infra_install_apply")
    assert call_order.index("infra_config") < call_order.index("server_install_apply")
    assert call_order.index("server_config") < call_order.index("infra_install_apply")
    assert call_order.index("server_config") < call_order.index("server_install_apply")


@_patch_all_steps
def test_install_stops_after_infra_config_error_and_does_not_delete_state(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """Even though infra_config itself never succeeds, the resolved admin credentials must still be
    persisted immediately - otherwise a step that keeps failing (e.g. the user repeatedly declining
    infra's own directory-exists confirmation) would force retyping them on every retry."""
    mock_load_state.return_value = None
    mock_infra_config.side_effect = InstallError("boom")

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_server_config.call_count == 0
    assert mock_infra_install_apply.call_count == 0
    assert mock_server_install_apply.call_count == 0
    assert mock_save_state.call_count == 1
    assert mock_save_state.call_args.args[0].completed_steps == []
    assert mock_save_state.call_args.args[0].admin == {
        "name": "Admin",
        "email": "admin@example.com",
        "password": "Sup3r$ecret!",
    }
    assert mock_delete_state.call_count == 0


@_patch_all_steps
def test_install_stops_after_infra_install_error_and_does_not_delete_state(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_infra_install_apply.side_effect = InstallError("boom")

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_infra_start.call_count == 0
    assert mock_server_install_apply.call_count == 0
    # +2: admin credentials + both config steps' own successful saves, all persisted before this failure.
    assert mock_save_state.call_count == 3
    assert mock_save_state.call_args.args[0].completed_steps == ["infra_config", "server_config"]
    assert mock_delete_state.call_count == 0


@_patch_all_steps
def test_install_stops_after_infra_start_error_does_not_call_service_install(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """infra install (apply) can succeed while infra start fails independently - this must
    surface as its own distinct step, not get lumped into "infra install"."""
    mock_load_state.return_value = None
    mock_infra_start.side_effect = typer.Exit(1)

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_infra_install_apply.call_count == 1
    assert mock_infra_post_start_action.call_count == 0
    assert mock_server_install_apply.call_count == 0
    # +3: admin credentials + both config steps + infra_install, all persisted before this failure.
    assert mock_save_state.call_count == 4
    assert mock_save_state.call_args.args[0].completed_steps == ["infra_config", "server_config", "infra_install"]


@_patch_all_steps
def test_install_stops_when_server_install_raises_does_not_call_login(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_server_install_apply.side_effect = InstallError("boom")

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_server_start.call_count == 0
    assert mock_get_token_from_login.call_count == 0
    assert mock_delete_state.call_count == 0


@_patch_all_steps
def test_install_bare_rerun_with_existing_state_starts_fresh(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A bare rerun (no --resume) over an unfinished previous run's state must not error out asking
    for --resume - once the user confirms discarding it, it runs a normal, complete fresh install,
    overwriting the state file up front instead of requiring the user to delete it by hand."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_config", "infra_install"],
        admin={"name": "Stale Admin", "email": "stale@example.com", "password": "St@leSecret1!"},
    )
    mock_echo.confirm.return_value = True
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()
    # save_state() is called repeatedly with the SAME install_state object, mutated in place as the
    # run progresses (admin set, completed_steps appended) - a plain call_args_list assertion would
    # see only its final, fully-mutated state, so snapshot each call's completed_steps/admin instead.
    saved_snapshots: list[tuple[list[str], dict | None]] = []
    mock_save_state.side_effect = lambda s: saved_snapshots.append((list(s.completed_steps), s.admin))

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=False)

    assert mock_echo.confirm.call_count == 1
    assert mock_echo.confirm.call_args.kwargs["default"] is True
    assert mock.call("Previous suite install state discarded; starting fresh.") in mock_echo.warning.call_args_list
    assert mock_infra_install_apply.call_count == 1
    assert mock_infra_install_apply.call_args == _infra_install_apply_call()
    assert mock_infra_start.call_count == 1
    assert mock_server_install_apply.call_args == _server_install_apply_call()
    # The stale state is overwritten immediately, before any step runs - not just lazily on the
    # first step's own save_state() call - so a crash before step 1 completes doesn't leave the OLD
    # run's progress (and stale admin) on disk. The new admin is then written immediately too, right
    # after resolving it, so it's never lost to a step that fails.
    assert saved_snapshots[0] == ([], None)
    assert saved_snapshots[1] == ([], {"name": "Admin", "email": "admin@example.com", "password": "Sup3r$ecret!"})
    assert mock_save_state.call_count == TOTAL_STEPS + 2


@_patch_all_steps
def test_install_bare_rerun_confirm_message_mentions_api_key_when_workspace_exists(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A prior run that got as far as creating the workspace holds a project API key that can
    never be retrieved again - the confirmation prompt must call that out specifically, not just
    generically mention discarding progress."""
    workspace = _make_workspace()
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=[step_id for step_id, _ in STEPS if step_id != "grant_model_access"],
        workspace=_workspace_to_dict(workspace),
    )
    mock_echo.confirm.return_value = True
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=False)

    message = mock_echo.confirm.call_args.args[0]
    assert "workspace API key" in message
    assert "never be retrieved again" in message


@_patch_all_steps
def test_install_bare_rerun_confirm_message_omits_api_key_when_no_workspace(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A prior run that never reached workspace creation has nothing irrecoverable to lose - the
    confirmation message shouldn't falsely warn about an API key that was never created."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_config", "infra_install"])
    mock_echo.confirm.return_value = True
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=False)

    message = mock_echo.confirm.call_args.args[0]
    assert "API key" not in message


@_patch_all_steps
def test_install_bare_rerun_declining_discard_continues_previous_install(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """Declining the discard confirmation must not error out or require a second invocation with
    --resume - it just continues the previous run in place, exactly as --resume would."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_config", "infra_install", "infra_start"],
        admin={"name": "Persisted Admin", "email": "persisted@example.com", "password": "Pers1sted$ecret!"},
    )
    mock_echo.confirm.return_value = False
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name=None, admin_email=None, admin_password=None, resume=False)

    assert mock_infra_install_apply.call_count == 0
    assert mock_infra_start.call_count == 0
    assert mock_server_install_apply.call_args == _server_install_apply_call()
    # Continuing here behaves exactly as --resume would (per this test's own docstring), so the
    # post-start-action calls must be quieted the same way a real --resume run's are - not left
    # noisy just because the local `resume` flag itself was never passed.
    assert mock_infra_post_start_action.call_args_list[0] == mock.call(
        _WORKSPACE_POST_START_ACTIONS[0], DF_INFRA_DIRECTORY, True
    )
    assert any(call == mock.call("Continuing the previous install instead.") for call in mock_echo.info.call_args_list)
    # No "state discarded" warning (nothing was discarded) - just the unconditional plaintext-
    # secrets notice that fires once per invocation, regardless of whether credentials were
    # freshly prompted or reused as-is from persisted state.
    assert mock_echo.warning.call_args_list == [mock.call(PLAINTEXT_WARNING)]


@_patch_all_steps
def test_install_bare_rerun_with_yes_flag_skips_confirmation_and_discards(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """--yes must skip the confirmation entirely (for scripted/CI use) and go straight to
    discarding the previous state, same as answering "yes" interactively."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_config", "infra_install"])
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()
    state.yes = True

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=False)

    assert mock_echo.confirm.call_count == 0
    assert mock_infra_install_apply.call_count == 1
    assert mock.call("Previous suite install state discarded; starting fresh.") in mock_echo.warning.call_args_list


@_patch_all_steps
def test_install_resume_skips_already_completed_steps_still_live(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """infra_install/infra_start skip because their live checks confirm the directory/container are
    still there (both mocks default to True via _patch_all_steps) - the live-state fix.
    infra_service_install/infra_model_install/server_post_start_action_0 always re-run regardless of
    completed_steps, relying on their own already-installed/already-exists idempotency."""
    completed = [
        "infra_config",
        "server_config",
        "infra_install",
        "infra_start",
        # Old, pre-template-flag fixed step ids (and, since the server side got the same dynamic
        # per-post-start-action treatment, "server_create_admin" too) - none of these match any
        # newly-computed step id (see test_install_resume_ignores_leftover_old_post_start_action_step_ids
        # below for the dedicated test of this), included here only because they were already part
        # of this test's fixture before those changes and are harmless noise for what this test
        # checks.
        "infra_service_install",
        "infra_model_install_chat",
        "infra_model_install_embedding",
        "infra_model_install_fast",
        "server_create_admin",
    ]
    mock_load_state.return_value = SuiteInstallState(completed_steps=list(completed))
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_config.call_count == 0
    assert mock_server_config.call_count == 0
    assert mock_infra_install_apply.call_count == 0
    assert mock_infra_start.call_count == 0
    assert mock_infra_post_start_action.call_count == 4
    # A --resume run repeats these calls (once per action) against the exact same, already-confirmed
    # connection - "Updated config/secrets" would just be noise, so it's quieted here.
    assert mock_infra_post_start_action.call_args_list == [
        mock.call(action, DF_INFRA_DIRECTORY, True) for action in _WORKSPACE_POST_START_ACTIONS
    ]
    assert mock_server_install_apply.call_count == 1
    assert mock_server_start.call_count == 1
    assert mock_server_post_start_action.call_count == 1


@_patch_all_steps
def test_install_infra_config_skip_reconstructs_from_persisted_dict(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """Once STEP_INFRA_CONFIG is done, --resume must reconstruct it from the persisted dict rather
    than re-resolving (re-prompting)."""
    persisted = {"api_key": "persisted-infra-key"}
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_config", "server_config"], infra_config=persisted, server_config={}
    )
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_config.call_count == 0
    assert mock_infra_config_from_dict.call_count == 1
    assert mock_infra_config_from_dict.call_args == mock.call(persisted)
    assert mock_infra_install_apply.call_args == _infra_install_apply_call()


@_patch_all_steps
def test_install_infra_start_reruns_when_container_no_longer_running_despite_completed_steps(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A container removed after infra_start succeeded (e.g. `docker rm`) must be detected live and
    restarted, not silently trusted as still up just because the step id is in completed_steps."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_config", "infra_install", "infra_start"])
    mock_install_directory_intact.return_value = True
    mock_is_service_running.return_value = False
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 0
    assert mock_infra_start.call_count == 1
    assert mock_is_service_running.call_args_list[0] == mock.call("infra", cwd=DF_INFRA_DIRECTORY)
    assert mock_infra_post_start_action.call_count == 4
    warning_messages = [call.args[0] for call in mock_echo.warning.call_args_list]
    assert (
        "Step 4/14: infra start... was marked complete previously, but is no longer detected as up; "
        "re-running." in warning_messages
    )


@_patch_all_steps
def test_install_infra_install_reruns_when_directory_missing_despite_completed_steps(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A fully deleted infra directory (e.g. `rm -rf ~/.deepfellow/infra`) must be detected live and
    reprovisioned, not silently trusted as still installed - the exact bug this fix resolves. It
    must reapply using the config already persisted by infra_config, not resolve a fresh one - see
    test_install_self_heal_does_not_re_resolve_infra_config below for that guarantee specifically."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_config", "infra_install"])
    mock_install_directory_intact.return_value = False
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 1
    assert mock_infra_install_apply.call_args == _infra_install_apply_call()
    warning_messages = [call.args[0] for call in mock_echo.warning.call_args_list]
    assert (
        "Step 3/14: infra install... was marked complete previously, but is no longer detected as up; "
        "re-running." in warning_messages
    )


@_patch_all_steps
def test_install_self_heal_does_not_re_resolve_infra_config(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A damaged-then-repaired infra directory must reapply the config already persisted by the
    infra_config step - not re-run infra_config (which would regenerate DF_INFRA_API_KEY via
    configure_uuid_key() reading a now-missing .env and silently invalidate server's already-
    resolved config). This is the fix for the bug the old forced-server-repair chain worked around."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_config", "server_config", "infra_install", "server_install"],
        infra_config={"api_key": "persisted-infra-key"},
        server_config={},
    )
    mock_install_directory_intact.side_effect = lambda directory: directory != DF_INFRA_DIRECTORY
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_config.call_count == 0
    assert mock_infra_config_from_dict.call_count == 1
    assert mock_infra_install_apply.call_count == 1
    assert mock_infra_install_apply.call_args == _infra_install_apply_call()


@_patch_all_steps
def test_install_infra_start_reruns_when_infra_self_heals_despite_container_still_running(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A deleted-then-reprovisioned infra directory (`rm -rf`'d without stopping the container)
    mints a brand-new DF_INFRA_API_KEY, but the old container - never actually stopped - still
    reports as running. infra_start must restart it to load the fresh key instead of trusting
    is_service_running alone, exactly like server_install/server_start already do when infra
    self-heals."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_config", "infra_install", "infra_start"])
    mock_install_directory_intact.return_value = False
    mock_is_service_running.return_value = True
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 1
    assert mock_infra_install_apply.call_args == _infra_install_apply_call()
    assert mock_infra_start.call_count == 1


@_patch_all_steps
def test_install_server_start_reruns_when_container_no_longer_running_despite_completed_steps(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    completed_through_server_start = [
        step_id for step_id, _ in STEPS if step_id not in ("server_post_start_action_0", "server_login")
    ][:10]
    mock_load_state.return_value = SuiteInstallState(completed_steps=completed_through_server_start)
    mock_install_directory_intact.return_value = True
    mock_is_service_running.side_effect = lambda service, cwd: service == "infra"  # infra up, server down
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_start.call_count == 0
    assert mock_server_start.call_count == 1
    assert mock.call("server", cwd=DF_SERVER_DIRECTORY) in mock_is_service_running.call_args_list


@_patch_all_steps
def test_install_server_install_reruns_when_directory_missing_despite_completed_steps(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    completed_through_server_install = [
        step_id for step_id, _ in STEPS if step_id not in ("server_start", "server_post_start_action_0", "server_login")
    ][:9]
    mock_load_state.return_value = SuiteInstallState(completed_steps=completed_through_server_install)
    mock_install_directory_intact.side_effect = lambda directory: directory != DF_SERVER_DIRECTORY
    mock_is_service_running.return_value = True
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 0
    assert mock_server_install_apply.call_count == 1
    assert mock_server_install_apply.call_args == _server_install_apply_call()


@_patch_all_steps
def test_install_infra_self_heal_no_longer_forces_server_repair(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """DFCLI-91's fix: repairing infra no longer regenerates DF_INFRA_API_KEY (config is reapplied,
    not re-resolved - see test_install_self_heal_does_not_re_resolve_infra_config), so an intact
    server install must stay skipped, not be force-repaired just because infra was."""
    completed_through_server_start = [
        step_id for step_id, _ in STEPS if step_id not in ("server_post_start_action_0", "server_login")
    ][:10]
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=completed_through_server_start,
        infra_config={"api_key": "persisted-infra-key"},
        server_config={},
    )
    mock_install_directory_intact.side_effect = lambda directory: directory != DF_INFRA_DIRECTORY
    mock_is_service_running.return_value = True
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 1
    assert mock_server_install_apply.call_count == 0
    assert mock_server_start.call_count == 0


@_patch_all_steps
def test_install_create_admin_always_executes_even_when_completed(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """create_admin is not cheaply live-checkable (an admin is a DB record, not a docker service) -
    it must always re-attempt, relying on create_admin_util's own idempotency for an existing admin."""
    completed_through_create_admin = [step_id for step_id, _ in STEPS if step_id not in ("server_login",)][:11]
    mock_load_state.return_value = SuiteInstallState(completed_steps=completed_through_create_admin)
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_server_post_start_action.call_count == 1


@_patch_all_steps
def test_install_grant_model_access_always_executes_even_when_completed(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """update_project() is a plain "set the models field" call, safe to always repeat - grant_model_access
    must re-attempt it even when already marked complete, unlike workspace_creation."""
    workspace = _make_workspace()
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=[step_id for step_id, _ in STEPS], workspace=_workspace_to_dict(workspace)
    )
    mock_get_token_from_login.return_value = "token"

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_create_workspace.call_count == 0
    assert mock_update_project.call_count == 1


def test_install_directory_intact_returns_true_when_directory_and_env_exist(tmp_path) -> None:
    (tmp_path / ".env").write_text("")

    assert _install_directory_intact(tmp_path) is True


def test_install_directory_intact_returns_false_when_env_file_missing(tmp_path) -> None:
    assert _install_directory_intact(tmp_path) is False


def test_install_directory_intact_returns_false_when_directory_missing(tmp_path) -> None:
    assert _install_directory_intact(tmp_path / "does-not-exist") is False


@_patch_all_steps
def test_install_resume_with_empty_completed_steps_does_not_force(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A crash mid infra-config (nothing persisted yet) means step 1 itself is not marked complete.
    --force-install is the single source of truth for both config steps' directory-exists guard - a
    bare --resume, regardless of completed_steps content, must never implicitly force one on."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=[])
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_config.call_args == mock.call(
        False,
        port=DF_INFRA_PORT,
        image=DF_INFRA_IMAGE,
        local_image=False,
        directory=DF_INFRA_DIRECTORY,
        docker_config=None,
        storage=DF_INFRA_STORAGE_DIR,
        docker_network=DF_INFRA_DOCKER_NETWORK,
        template="workspace",
        explicitly_provided=set(),
    )
    assert mock_server_config.call_args.args[4] is False  # force_install


@_patch_all_steps
def test_install_resume_with_partial_completed_steps_does_not_force(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """Same as above, with infra_config/infra_install already completed (and still verified intact,
    so both are skipped outright) - server_config must still default to force_install=False, not
    inherit force from infra having succeeded."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_config", "infra_install"])
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_config.call_count == 0
    assert mock_infra_install_apply.call_count == 0
    assert mock_server_config.call_args.args[4] is False  # force_install


@_patch_all_steps
def test_install_force_install_flag_is_passed_to_infra_and_server_config(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """--force-install is the single source of truth for both infra and server config's
    directory-exists guard - not derived from --resume/prior state in any way."""
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        force_install=True,
    )

    assert mock_infra_config.call_args.args[0] is True
    assert mock_server_config.call_args.args[4] is True  # force_install


@_patch_all_steps
def test_install_resume_with_no_state_file_runs_fresh(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 1
    assert mock_infra_install_apply.call_args == _infra_install_apply_call()
    assert mock_server_install_apply.call_args == _server_install_apply_call()


@_patch_all_steps
def test_install_resume_reuses_persisted_workspace_without_recreating(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    workspace = _make_workspace(organization_id="org-1", project_id="project-1")
    all_but_grant = [step_id for step_id, _ in STEPS if step_id != "grant_model_access"]
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=all_but_grant, workspace=_workspace_to_dict(workspace)
    )
    mock_get_token_from_login.return_value = "token"

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_create_workspace.call_count == 0
    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args.args[2:4] == ("org-1", "project-1")
    assert mock_echo.info.call_args_list[-1] == mock.call(str(workspace))


def test_workspace_from_dict_raises_install_error_on_missing_keys() -> None:
    from deepfellow.suite.utils.install import _workspace_from_dict

    with pytest.raises(InstallError, match="invalid or corrupted"):
        _workspace_from_dict({"organization": {"id": "org-1"}})  # missing "project"/"api_key"


def test_workspace_from_dict_raises_install_error_on_wrong_shape() -> None:
    """Not just missing keys - a value of the wrong type (e.g. a string instead of a dict) must
    also surface as InstallError, not a bare TypeError from Organization(**"not-a-dict")."""
    from deepfellow.suite.utils.install import _workspace_from_dict

    with pytest.raises(InstallError, match="invalid or corrupted"):
        _workspace_from_dict({"organization": "not-a-dict", "project": {}, "api_key": {}})


def test_workspace_from_dict_raises_install_error_on_non_dict_api_key() -> None:
    """A non-dict api_key raises AttributeError inside ApiKey.from_data() (it calls
    data.get("value") on it) rather than TypeError/KeyError - a distinct failure mode from the
    other two shape-validation tests above that must still surface as a clean InstallError.
    organization/project are otherwise valid so the failure is isolated to api_key."""
    from deepfellow.suite.utils.install import _workspace_from_dict

    data = _workspace_to_dict(_make_workspace())
    data["api_key"] = "not-a-dict"

    with pytest.raises(InstallError, match="invalid or corrupted"):
        _workspace_from_dict(data)


def test_infra_config_to_dict_from_dict_round_trips() -> None:
    config = _make_infra_config()

    result = _infra_config_from_dict(_infra_config_to_dict(config))

    assert result == config


def test_infra_config_to_dict_serializes_path_fields_as_strings() -> None:
    config = _make_infra_config()

    data = _infra_config_to_dict(config)

    assert data["directory"] == str(config.directory)
    assert data["docker_config"] == str(config.docker_config)
    assert data["storage_dir"] == str(config.storage_dir)


def test_infra_config_from_dict_raises_install_error_on_missing_keys() -> None:
    with pytest.raises(InstallError, match="invalid or corrupted"):
        _infra_config_from_dict({"directory": "/tmp/infra"})


def test_infra_config_from_dict_raises_install_error_on_wrong_shape() -> None:
    data = _infra_config_to_dict(_make_infra_config())
    del data["api_key"]

    with pytest.raises(InstallError, match="invalid or corrupted"):
        _infra_config_from_dict(data)


def test_server_config_to_dict_from_dict_round_trips() -> None:
    config = _make_server_config()

    result = _server_config_from_dict(_server_config_to_dict(config))

    assert result == config


def test_server_config_to_dict_serializes_directory_as_string() -> None:
    config = _make_server_config()

    data = _server_config_to_dict(config)

    assert data["directory"] == str(config.directory)
    assert data["otel"] == {"envs": {}, "docker_compose": {}, "collector_config": None}
    assert data["falkordb"] == {"envs": {}, "docker_compose": {}}


def test_server_config_from_dict_raises_install_error_on_missing_keys() -> None:
    with pytest.raises(InstallError, match="invalid or corrupted"):
        _server_config_from_dict({"directory": "/tmp/server"})


def test_server_config_from_dict_raises_install_error_on_missing_otel() -> None:
    data = _server_config_to_dict(_make_server_config())
    del data["otel"]

    with pytest.raises(InstallError, match="invalid or corrupted"):
        _server_config_from_dict(data)


def test_server_config_from_dict_raises_install_error_on_missing_falkordb() -> None:
    data = _server_config_to_dict(_make_server_config())
    del data["falkordb"]

    with pytest.raises(InstallError, match="invalid or corrupted"):
        _server_config_from_dict(data)


@_patch_all_steps
def test_install_resume_with_corrupted_persisted_workspace_fails_cleanly(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A resumed run whose persisted `workspace` dict is malformed (e.g. corrupted by a crash
    mid-write) must fail with a clean InstallError, not an unhandled traceback - on_skip() is
    exercised on this exact "workspace_creation already completed" path, and must be guarded the
    same way func() already is."""
    all_but_grant = [step_id for step_id, _ in STEPS if step_id != "grant_model_access"]
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=all_but_grant, workspace={"organization": {"id": "org-1"}}
    )
    mock_get_token_from_login.return_value = "token"

    with pytest.raises(InstallError, match="Installation failed"):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_create_workspace.call_count == 0
    assert mock_update_project.call_count == 0


@_patch_all_steps
def test_install_resume_with_corrupted_persisted_infra_config_fails_cleanly(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A resumed run whose persisted `infra_config` dict is malformed must fail with a clean
    InstallError, not an unhandled traceback - `_infra_config_on_skip()` (the `on_skip` for
    STEP_INFRA_CONFIG) must be guarded by `_run_step()` the same way `func()` already is, exactly
    like `test_install_resume_with_corrupted_persisted_workspace_fails_cleanly` above. This proves
    the wiring, not `_infra_config_from_dict()` itself - see the dedicated
    `test_infra_config_from_dict_raises_install_error_on_*` tests for that."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_config"], infra_config={"bad": "shape"})
    mock_infra_config_from_dict.side_effect = InstallError(
        "Suite install state file's persisted infra configuration is invalid or corrupted"
    )

    with pytest.raises(InstallError, match="Installation failed"):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_server_config.call_count == 0
    assert mock_infra_install_apply.call_count == 0


@_patch_all_steps
def test_install_resume_with_corrupted_persisted_server_config_fails_cleanly(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """Same as above, for STEP_SERVER_CONFIG's `on_skip` (`_server_config_on_skip()`)."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_config", "server_config"], server_config={"bad": "shape"}
    )
    mock_server_config_from_dict.side_effect = InstallError(
        "Suite install state file's persisted server configuration is invalid or corrupted"
    )

    with pytest.raises(InstallError, match="Installation failed"):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 0
    assert mock_server_install_apply.call_count == 0


@_patch_all_steps
def test_install_resume_with_pre_change_state_file_falls_back_to_one_time_reprompt(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A state file from before infra_config/server_config existed (DFCLI-91) has "infra_install"/
    "server_install" marked done but no persisted infra_config/server_config. --resume must fall
    back to resolving both once (re-prompting) instead of crashing, and then skip the now-redundant
    apply steps since the directories are still intact."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=[
            "infra_install",
            "infra_start",
            "infra_service_install",
            "infra_model_install_chat",
            "infra_model_install_embedding",
            "infra_model_install_fast",
            "server_install",
            "server_start",
        ],
        infra_config=None,
        server_config=None,
    )
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_config.call_count == 1
    assert mock_server_config.call_count == 1
    assert mock_infra_install_apply.call_count == 0
    assert mock_server_install_apply.call_count == 0


@_patch_all_steps
def test_install_resume_reuses_persisted_admin_without_prompting(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A `--resume` run must reuse the admin credentials a prior run already collected (whether
    typed interactively or passed via --admin-*/env vars) instead of prompting for them again."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_config"],
        admin={"name": "Persisted Admin", "email": "persisted@example.com", "password": "Pers1sted$ecret!"},
    )
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name=None, admin_email=None, admin_password=None, resume=True)

    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_server_config.call_args.args[1:4] == ("Persisted Admin", "persisted@example.com", "Pers1sted$ecret!")
    assert mock_get_token_from_login.call_args.kwargs["email"] == "persisted@example.com"
    assert mock_get_token_from_login.call_args.kwargs["password"] == "Pers1sted$ecret!"
    # A pure passthrough of the persisted value - no flag, no prompt - must not count as an
    # override: _server_post_start_action() would otherwise warn about a no-op that was actually
    # expected (the same admin as before, not a value the user just supplied this run).
    assert mock_server_post_start_action.call_args == mock.call(
        _SERVER_WORKSPACE_POST_START_ACTIONS[0],
        DF_SERVER_DIRECTORY,
        "Persisted Admin",
        "persisted@example.com",
        "Pers1sted$ecret!",
        False,
    )


@_patch_all_steps
def test_install_resume_admin_flag_overrides_persisted_credentials(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """An explicit --admin-password (or --admin-name/--admin-email) on the resuming invocation must
    win over whatever a prior run persisted, same as it wins over any other fallback source."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_config"],
        admin={"name": "Persisted Admin", "email": "persisted@example.com", "password": "Pers1sted$ecret!"},
    )
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name=None, admin_email=None, admin_password="N3w$ecret!", resume=True)

    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_server_config.call_args.args[1:4] == ("Persisted Admin", "persisted@example.com", "N3w$ecret!")
    assert mock_save_state.call_args_list[0].args[0].admin == {
        "name": "Persisted Admin",
        "email": "persisted@example.com",
        "password": "N3w$ecret!",
    }


@_patch_all_steps
def test_install_non_interactive_resume_uses_persisted_admin_without_error(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """--non-interactive must not require --admin-* on a `--resume` run once a prior run already
    persisted them - only a genuinely missing value (covered by the existing "missing" test) should
    raise."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_config"],
        admin={"name": "Persisted Admin", "email": "persisted@example.com", "password": "Pers1sted$ecret!"},
    )
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()
    state.non_interactive = True

    install(admin_name=None, admin_email=None, admin_password=None, resume=True)

    assert mock_server_config.call_args.args[1:4] == ("Persisted Admin", "persisted@example.com", "Pers1sted$ecret!")


@_patch_all_steps
def test_install_persists_resolved_admin_credentials_on_fresh_run(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """The resolved admin credentials must be on `install_state` by the very first `save_state()`
    call, so a crash on any later step already has them available for a subsequent `--resume`."""
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_save_state.call_args_list[0].args[0].admin == {
        "name": "Admin",
        "email": "admin@example.com",
        "password": "Sup3r$ecret!",
    }


@_patch_all_steps
def test_install_warns_about_plaintext_secrets_exactly_once(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """The plaintext-secrets notice must fire exactly once per invocation, at the single point
    where admin credentials get persisted, and must now also mention the infra/server config that
    gets persisted once resolved - not on every one of the ~14 subsequent save_state() calls that
    just persist step progress."""
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    plaintext_warnings = [call for call in mock_echo.warning.call_args_list if "plain text" in call.args[0]]
    assert len(plaintext_warnings) == 1
    assert plaintext_warnings[0] == mock.call(PLAINTEXT_WARNING)
    assert "infra/server installation configuration" in plaintext_warnings[0].args[0]
    assert mock_save_state.call_count > 1


@_patch_all_steps
def test_install_resumed_create_admin_step_succeeds_and_continues(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """create_admin is idempotent (see server/utils/users.py) - a resumed run whose admin already
    existed from before the interruption must succeed, not abort."""
    completed_through_server_start = [
        step_id for step_id, _ in STEPS if step_id not in ("server_post_start_action_0", "server_login")
    ][:10]
    mock_load_state.return_value = SuiteInstallState(completed_steps=completed_through_server_start)
    mock_server_post_start_action.return_value = None  # idempotent no-op, not an error
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_server_post_start_action.call_count == 1
    assert mock_get_token_from_login.call_count == 1


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.load_state")
def test_install_prompt_failure_is_translated_to_install_error(
    mock_load_state: Mock, mock_assert_docker: Mock, mock_echo: Mock
) -> None:
    mock_load_state.return_value = None
    mock_echo.prompt_until_valid.side_effect = typer.Exit(1)

    with pytest.raises(InstallError):
        install(admin_name=None, admin_email=None, admin_password=None)


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.load_state")
def test_install_non_interactive_reports_all_missing_admin_values(
    mock_load_state: Mock, mock_assert_docker: Mock, mock_echo: Mock
) -> None:
    mock_load_state.return_value = None
    state.non_interactive = True

    with pytest.raises(InstallError) as exc_info:
        install(admin_name=None, admin_email=None, admin_password=None)

    assert str(exc_info.value) == (
        "suite install is missing name, email, password; --non-interactive has no prompt to fall "
        "back on. Pass --admin-name/--admin-email/--admin-password"
    )


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.load_state")
def test_install_translates_bad_parameter_to_install_error(
    mock_load_state: Mock, mock_assert_docker: Mock, mock_echo: Mock
) -> None:
    """A caller outside Click (e.g. the suite Typer command) sees a message-carrying
    InstallError instead of an unhandled, message-less typer.BadParameter - mirroring how
    server's install() is made safe by the same @translate_to_install_error decorator."""
    mock_load_state.return_value = None
    mock_echo.prompt_until_valid.side_effect = typer.BadParameter("Invalid admin email")

    with pytest.raises(InstallError, match="Invalid admin email"):
        install(admin_name=None, admin_email=None, admin_password=None)


@_patch_all_steps
def test_install_translates_step_exit_to_install_error(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A step's typer.Exit (already normalized and re-raised by run_step) must surface from
    install() as InstallError, not an unhandled typer.Exit - the same @translate_to_install_error
    contract as server's install()."""
    mock_load_state.return_value = None
    mock_infra_install_apply.side_effect = typer.Exit(1)

    with pytest.raises(InstallError, match="Installation failed"):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")


@_patch_all_steps
def test_install_prompted_credentials_are_reused_for_server_config_and_login(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_echo.prompt_until_valid.side_effect = ["Prompted Admin", "prompted@example.com", "Pr0mpted$ecret!"]
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name=None, admin_email=None, admin_password=None)

    assert mock_server_config.call_args.args[1:4] == ("Prompted Admin", "prompted@example.com", "Pr0mpted$ecret!")
    assert mock_get_token_from_login.call_args.kwargs["email"] == "prompted@example.com"
    assert mock_get_token_from_login.call_args.kwargs["password"] == "Pr0mpted$ecret!"
    # Typed at a prompt is just as deliberate as an explicit --admin-* flag: the user is
    # supplying an admin identity for this run, not passively reusing a persisted one, so it
    # must count as an override too - otherwise a value that turns out to target an
    # already-existing account gets silently discarded with no warning (see the concrete failure
    # scenario in the !311 review: a mistyped password at this exact prompt led to a confusing,
    # unrelated login failure two steps later instead of a clear warning here).
    assert mock_server_post_start_action.call_args == mock.call(
        _SERVER_WORKSPACE_POST_START_ACTIONS[0],
        DF_SERVER_DIRECTORY,
        "Prompted Admin",
        "prompted@example.com",
        "Pr0mpted$ecret!",
        True,
    )


@_patch_all_steps
def test_install_checks_docker_before_prompting(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """assert_docker() runs before the admin-credential prompts, so a missing/unusable Docker
    installation is caught immediately instead of after the user answers those prompts."""
    call_order: list[str] = []

    def _record_prompt(*args: object, **kwargs: object) -> str:
        call_order.append("prompt")
        return "value"

    mock_assert_docker.side_effect = lambda: call_order.append("assert_docker")
    mock_echo.prompt_until_valid.side_effect = _record_prompt
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name=None, admin_email=None, admin_password=None)

    assert call_order[0] == "assert_docker"
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.assert_docker")
def test_install_stops_when_docker_check_fails(mock_assert_docker: Mock, mock_echo: Mock) -> None:
    mock_assert_docker.side_effect = typer.Exit(1)

    with pytest.raises(InstallError, match="Installation failed"):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_echo.prompt_until_valid.call_count == 0


@_patch_all_steps
def test_install_forwards_distinct_infra_and_server_ports_independently(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_env_get.return_value = "9001"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        infra_port=9000,
        server_port=9001,
    )

    assert mock_infra_config.call_args.kwargs["port"] == 9000
    assert mock_server_config.call_args.kwargs["port"] == 9001
    # server_url used for login/workspace-creation must follow the actually-resolved server port.
    assert mock_get_token_from_login.call_args.args[1] == "http://localhost:9001"


@_patch_all_steps
def test_install_uses_resolved_server_port_over_cli_value_for_login_url(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """If server config resolves a different port than the raw CLI value - e.g. restored from a
    prior install's own .env because --server-port wasn't passed this time - server_url must follow
    the actually-resolved port (read back via env_get), not the value install() was called with, or
    login/workspace-creation would target a server that isn't listening there."""
    mock_load_state.return_value = None
    mock_env_get.return_value = "9002"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_server_config.call_args.kwargs["port"] == DF_SERVER_PORT
    assert mock_get_token_from_login.call_args.args[1] == "http://localhost:9002"


@_patch_all_steps
def test_install_forwards_docker_network_to_both_infra_and_server_config(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        docker_network="my-custom-net",
    )

    assert mock_infra_config.call_args.kwargs["docker_network"] == "my-custom-net"
    assert mock_server_config.call_args.kwargs["docker_network"] == "my-custom-net"


@_patch_all_steps
def test_install_forwards_falkordb_options_to_server_config(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        falkordb_active=True,
        falkordb_url="my-falkordb:6379",
        falkordb_username="graphuser",
        falkordb_password="graphpass",
    )

    assert mock_server_config.call_args.kwargs["falkordb_active"] is True
    assert mock_server_config.call_args.kwargs["falkordb_url"] == "my-falkordb:6379"
    assert mock_server_config.call_args.kwargs["falkordb_username"] == "graphuser"
    assert mock_server_config.call_args.kwargs["falkordb_password"] == "graphpass"


@_patch_all_steps
def test_install_falkordb_disabled_by_default(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_server_config.call_args.kwargs["falkordb_active"] is False


@_patch_all_steps
def test_install_forwards_mongodb_port_and_credentials_to_server_config(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        mongodb_port=27018,
        mongodb_username="dfuser",
        mongodb_password="dfpass",
    )

    assert mock_server_config.call_args.kwargs["mongodb_port"] == 27018
    assert mock_server_config.call_args.kwargs["mongodb_username"] == "dfuser"
    assert mock_server_config.call_args.kwargs["mongodb_password"] == "dfpass"


@_patch_all_steps
def test_install_forwards_otel_local_to_server_config(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", otel_local=True)

    assert mock_server_config.call_args.kwargs["otel_local"] is True


@_patch_all_steps
def test_install_forwards_custom_infra_and_server_directories(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A custom --infra-directory/--server-directory must be reflected in the decomposed steps
    that operate against those specific directories (config, start, create-admin, service and
    model install), and a custom server directory must be forwarded to
    set_default_server_directory() too."""
    custom_infra_directory = Path("/custom/infra")
    custom_server_directory = Path("/custom/server")
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        infra_directory=custom_infra_directory,
        server_directory=custom_server_directory,
    )

    assert mock_infra_config.call_args.kwargs["directory"] == custom_infra_directory
    assert mock_infra_start.call_args == mock.call(custom_infra_directory)
    assert mock_infra_post_start_action.call_args_list[0] == mock.call(
        _WORKSPACE_POST_START_ACTIONS[0], custom_infra_directory, False
    )
    assert mock_server_config.call_args.kwargs["directory"] == custom_server_directory
    assert mock_server_start.call_args == mock.call(custom_server_directory)
    assert mock_server_post_start_action.call_args == mock.call(
        _SERVER_WORKSPACE_POST_START_ACTIONS[0],
        custom_server_directory,
        "Admin",
        "admin@example.com",
        "Sup3r$ecret!",
        True,
    )
    assert mock_set_default_server_directory.call_args == mock.call(custom_server_directory, force=False)
    assert mock_env_get.call_args == mock.call(custom_server_directory / ".env", "DF_SERVER_PORT")


@_patch_all_steps
def test_install_maps_explicitly_provided_to_infra_and_server_port_only(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """explicitly_provided={"infra_port"} must reach only infra_config's own "port" key,
    not server_config's - the two ports are independent despite sharing the same target
    field name."""
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        explicitly_provided={"infra_port"},
    )

    assert mock_infra_config.call_args.kwargs["explicitly_provided"] == {"port"}
    assert mock_server_config.call_args.kwargs["explicitly_provided"] == set()


@_patch_all_steps
def test_install_maps_explicitly_provided_docker_network_to_both(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        explicitly_provided={"docker_network"},
    )

    assert mock_infra_config.call_args.kwargs["explicitly_provided"] == {"docker_network"}
    assert mock_server_config.call_args.kwargs["explicitly_provided"] == {"docker_network"}


@_patch_all_steps
def test_install_warns_when_infra_config_flags_ignored_because_step_skipped(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """--infra-port (etc.) passed on a --resume run against an already-installed infra must warn
    that it was ignored, mirroring _server_post_start_action's admin_overridden warning - the step is
    skipped outright (is_done), so its config flags never reach infra_config()."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_config", "infra_install"])
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        resume=True,
        infra_port=9000,
        explicitly_provided={"infra_port"},
    )

    assert mock_infra_install_apply.call_count == 0
    warning_messages = [call.args[0] for call in mock_echo.warning.call_args_list]
    assert any("--infra-port" in msg and "infra is already installed" in msg for msg in warning_messages)


@_patch_all_steps
def test_install_warns_when_server_config_flags_ignored_because_step_skipped(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """Same as above, for one of server config's own flags - not one of the 3 fields that also
    participate in template-merge precedence, to prove the warning isn't limited to those."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_config", "server_config", "infra_install", "server_install"]
    )
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        resume=True,
        mongodb_port=27018,
        explicitly_provided={"mongodb_port"},
    )

    assert mock_server_install_apply.call_count == 0
    warning_messages = [call.args[0] for call in mock_echo.warning.call_args_list]
    assert any("--mongodb-port" in msg and "server is already installed" in msg for msg in warning_messages)


@_patch_all_steps
def test_install_warns_when_infra_config_flag_ignored_even_if_install_step_reruns(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """STEP_INFRA_CONFIG is the only step that ever reads --infra-port (etc.) - once it's done, it
    stays skipped (reconstructed from the persisted config) regardless of what happens to
    STEP_INFRA_INSTALL afterward. So a flag passed here is ignored - and warned about - even when
    infra_install itself reruns (e.g. a self-heal after its directory went missing): the rerun
    still reapplies the OLD persisted config, not one re-resolved with the new flag."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_config", "infra_install"])
    mock_install_directory_intact.return_value = False
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        resume=True,
        infra_port=9000,
        explicitly_provided={"infra_port"},
    )

    assert mock_infra_install_apply.call_count == 1
    warning_messages = [call.args[0] for call in mock_echo.warning.call_args_list]
    assert any("--infra-port" in msg and "infra is already installed" in msg for msg in warning_messages)


@mock.patch("deepfellow.suite.utils.install.echo")
def test_warn_config_flags_ignored_lists_every_overridden_flag(mock_echo: Mock) -> None:
    from deepfellow.suite.utils.install import _warn_config_flags_ignored

    _warn_config_flags_ignored(
        "infra", {"infra_port", "infra_directory", "server_port"}, {"infra_port", "infra_directory"}
    )

    assert mock_echo.warning.call_count == 1
    message = mock_echo.warning.call_args.args[0]
    assert "--infra-directory" in message
    assert "--infra-port" in message
    assert "infra is already installed" in message


@mock.patch("deepfellow.suite.utils.install.echo")
def test_warn_config_flags_ignored_no_warning_when_nothing_overridden(mock_echo: Mock) -> None:
    from deepfellow.suite.utils.install import _warn_config_flags_ignored

    _warn_config_flags_ignored("infra", {"server_port"}, {"infra_port", "infra_directory"})

    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.suite.utils.install.infra_resolve")
@mock.patch("deepfellow.suite.utils.install.infra_inspect")
def test_infra_config_forwards_the_given_template(mock_infra_inspect: Mock, mock_infra_resolve: Mock) -> None:
    """The `template` argument must be forwarded through, not hardcoded - proven by passing a value
    other than the default "workspace" and asserting infra_inspect() received that exact value."""
    from deepfellow.suite.utils.install import _infra_config

    _infra_config(
        force_install=True,
        port=DF_INFRA_PORT,
        image=DF_INFRA_IMAGE,
        local_image=False,
        directory=DF_INFRA_DIRECTORY,
        docker_config=None,
        storage=DF_INFRA_STORAGE_DIR,
        docker_network=DF_INFRA_DOCKER_NETWORK,
        template="custom-template",
        explicitly_provided=set(),
    )

    assert mock_infra_inspect.call_args.kwargs["template"] == "custom-template"
    assert mock_infra_inspect.call_args.kwargs["force_install"] is True
    assert mock_infra_resolve.call_args.args[0] == mock_infra_inspect.return_value
    assert mock_infra_resolve.call_args.kwargs["docker_config"] == DF_INFRA_DIRECTORY / "docker-config.json"


@mock.patch("deepfellow.suite.utils.install.infra_resolve")
@mock.patch("deepfellow.suite.utils.install.infra_inspect")
def test_infra_config_returns_resolve_result(mock_infra_inspect: Mock, mock_infra_resolve: Mock) -> None:
    from deepfellow.suite.utils.install import _infra_config

    result = _infra_config(
        force_install=False,
        port=DF_INFRA_PORT,
        image=DF_INFRA_IMAGE,
        local_image=False,
        directory=DF_INFRA_DIRECTORY,
        docker_config=None,
        storage=DF_INFRA_STORAGE_DIR,
        docker_network=DF_INFRA_DOCKER_NETWORK,
        template="workspace",
        explicitly_provided=set(),
    )

    assert result == mock_infra_resolve.return_value


@mock.patch("deepfellow.suite.utils.install.infra_inspect")
def test_infra_config_translates_bad_parameter_to_install_error(mock_infra_inspect: Mock) -> None:
    """`_infra_config()` is decorated with `@translate_to_install_error` just like every other
    step function, so a raw typer.BadParameter/OSError from inspect()/resolve() (e.g. get_socket(),
    ensure_directory()) surfaces here as a clean InstallError - caught by _run_step()'s own
    per-step "Step N/TOTAL (name) failed: ..." message - instead of only being caught much later by
    install()'s own outer decorator, which has no idea which step actually failed."""
    from deepfellow.suite.utils.install import _infra_config

    mock_infra_inspect.side_effect = typer.BadParameter("bad template")

    with pytest.raises(InstallError, match="bad template"):
        _infra_config(
            force_install=False,
            port=DF_INFRA_PORT,
            image=DF_INFRA_IMAGE,
            local_image=False,
            directory=DF_INFRA_DIRECTORY,
            docker_config=None,
            storage=DF_INFRA_STORAGE_DIR,
            docker_network=DF_INFRA_DOCKER_NETWORK,
            template="workspace",
            explicitly_provided=set(),
        )


@mock.patch("deepfellow.suite.utils.install.infra_resolve")
@mock.patch("deepfellow.suite.utils.install.infra_inspect")
def test_infra_config_translates_os_error_to_install_error(mock_infra_inspect: Mock, mock_infra_resolve: Mock) -> None:
    from deepfellow.suite.utils.install import _infra_config

    mock_infra_resolve.side_effect = OSError("disk full")

    with pytest.raises(InstallError, match="disk full"):
        _infra_config(
            force_install=False,
            port=DF_INFRA_PORT,
            image=DF_INFRA_IMAGE,
            local_image=False,
            directory=DF_INFRA_DIRECTORY,
            docker_config=None,
            storage=DF_INFRA_STORAGE_DIR,
            docker_network=DF_INFRA_DOCKER_NETWORK,
            template="workspace",
            explicitly_provided=set(),
        )


@mock.patch("deepfellow.suite.utils.install.infra_apply")
@mock.patch("deepfellow.suite.utils.install.ensure_directory")
def test_infra_install_apply_ensures_directory_then_applies(
    mock_ensure_directory: Mock, mock_infra_apply: Mock
) -> None:
    from deepfellow.suite.utils.install import _infra_install_apply

    config = _make_infra_config()

    _infra_install_apply(config)

    assert mock_ensure_directory.call_args == mock.call(config.directory, force_install=True)
    assert mock_infra_apply.call_args == mock.call(config, will_auto_start=True)


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.start_infra")
def test_infra_start_wraps_docker_network_error(mock_start_infra: Mock, mock_echo: Mock) -> None:
    """@translate_to_install_error generic-izes the re-raised typer.Exit's message (matching
    infra install()'s own pre-existing behavior for this exact code path) - the specific reason is
    only surfaced as a console side effect via echo.error, not embedded in the raised exception."""
    from deepfellow.common.exceptions import DockerNetworkError
    from deepfellow.suite.utils.install import _infra_start

    mock_start_infra.side_effect = DockerNetworkError("no network")

    with pytest.raises(InstallError, match="Installation failed"):
        _infra_start(DF_INFRA_DIRECTORY)

    assert mock_echo.error.call_args == mock.call("Failed to start infra: no network")


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.start_infra")
def test_infra_start_reraises_original_error_in_debug_mode(mock_start_infra: Mock, mock_echo: Mock) -> None:
    """Matches server install()'s own start_server error handling (and _server_start's own mirror
    fix): --debug surfaces the specific DockerNetworkError message via InstallError, instead of
    the generic "Installation failed" one @translate_to_install_error substitutes for a bare
    typer.Exit (see the non-debug counterpart, test_infra_start_wraps_docker_network_error)."""
    from deepfellow.common.exceptions import DockerNetworkError
    from deepfellow.suite.utils.install import _infra_start

    state.debug = True
    mock_start_infra.side_effect = DockerNetworkError("no network")

    with pytest.raises(InstallError, match="no network"):
        _infra_start(DF_INFRA_DIRECTORY)


@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.infra_dispatch_post_start_action")
def test_infra_post_start_action_dispatches_a_service_install_action_with_localhost_url(
    mock_dispatch: Mock, mock_env_get: Mock
) -> None:
    from deepfellow.suite.utils.install import _infra_post_start_action

    mock_env_get.return_value = "9999"
    service_action = _WORKSPACE_POST_START_ACTIONS[0]

    _infra_post_start_action(service_action, DF_INFRA_DIRECTORY, quiet=True)

    dispatched = mock_dispatch.call_args.args[0]
    assert dispatched["function"] == service_action["function"] == "infra.service.install"
    assert dispatched["kwargs"] == {**service_action["kwargs"], "server": "http://localhost:9999", "quiet": True}


@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.infra_dispatch_post_start_action")
def test_infra_post_start_action_dispatches_a_model_install_action(mock_dispatch: Mock, mock_env_get: Mock) -> None:
    from deepfellow.suite.utils.install import _infra_post_start_action

    mock_env_get.return_value = None
    model_action = _WORKSPACE_POST_START_ACTIONS[1]

    _infra_post_start_action(model_action, DF_INFRA_DIRECTORY, quiet=False)

    dispatched = mock_dispatch.call_args.args[0]
    assert dispatched["function"] == model_action["function"] == "infra.model.install"
    assert dispatched["kwargs"] == {**model_action["kwargs"], "server": mock.ANY, "quiet": False}


def _server_config_kwargs(**overrides: object) -> dict:
    base = {
        "port": DF_SERVER_PORT,
        "image": DF_SERVER_IMAGE,
        "local_image": False,
        "directory": DF_SERVER_DIRECTORY,
        "docker_network": DF_INFRA_DOCKER_NETWORK,
        "mongodb_port": DF_MONGO_PORT,
        "mongodb_username": "",
        "mongodb_password": "",
        "falkordb_active": False,
        "falkordb_url": DF_FALKORDB_URL,
        "falkordb_username": "",
        "falkordb_password": "",
        "otel_local": False,
        "template": "workspace",
        "explicitly_provided": set(),
    }
    base.update(overrides)
    return base


@mock.patch("deepfellow.suite.utils.install.server_resolve")
@mock.patch("deepfellow.suite.utils.install.server_inspect")
def test_server_config_forwards_the_given_template_and_infra_api_key(
    mock_server_inspect: Mock, mock_server_resolve: Mock
) -> None:
    """`template` must be forwarded through, not hardcoded - proven by passing a value other than
    the default "workspace" and asserting server_inspect() received that exact value."""
    from deepfellow.suite.utils.install import _server_config

    infra_config = _make_infra_config(api_key="infra-api-key")

    _server_config(
        infra_config,
        "Admin",
        "admin@example.com",
        "Sup3r$ecret!",
        True,
        **_server_config_kwargs(template="custom-template"),
    )

    assert mock_server_inspect.call_args.kwargs["template"] == "custom-template"
    assert mock_server_inspect.call_args.kwargs["force_install"] is True
    assert mock_server_inspect.call_args.kwargs["admin_email"] == "admin@example.com"
    assert mock_server_resolve.call_args.kwargs["infra_api_key"] == "infra-api-key"
    # infra_api_key is always freshly resolved for the infra installation this suite run is about
    # to perform, never a CLI flag - it must never be silently outranked by a future template's
    # own "infra_api_key", unlike port/docker_network, whose explicit status genuinely depends on
    # what the user passed.
    assert "infra_api_key" in mock_server_resolve.call_args.kwargs["explicitly_provided"]


@mock.patch("deepfellow.suite.utils.install.server_resolve")
@mock.patch("deepfellow.suite.utils.install.server_inspect")
def test_server_config_returns_resolve_result(mock_server_inspect: Mock, mock_server_resolve: Mock) -> None:
    from deepfellow.suite.utils.install import _server_config

    result = _server_config(
        _make_infra_config(), "Admin", "admin@example.com", "Sup3r$ecret!", False, **_server_config_kwargs()
    )

    assert result == mock_server_resolve.return_value


@mock.patch("deepfellow.suite.utils.install.server_inspect")
def test_server_config_translates_bad_parameter_to_install_error(mock_server_inspect: Mock) -> None:
    """`_server_config()` is decorated with `@translate_to_install_error` just like every other
    step function - see `test_infra_config_translates_bad_parameter_to_install_error()`."""
    from deepfellow.suite.utils.install import _server_config

    mock_server_inspect.side_effect = typer.BadParameter("bad template")

    with pytest.raises(InstallError, match="bad template"):
        _server_config(
            _make_infra_config(), "Admin", "admin@example.com", "Sup3r$ecret!", False, **_server_config_kwargs()
        )


@mock.patch("deepfellow.suite.utils.install.server_resolve")
@mock.patch("deepfellow.suite.utils.install.server_inspect")
def test_server_config_translates_os_error_to_install_error(
    mock_server_inspect: Mock, mock_server_resolve: Mock
) -> None:
    from deepfellow.suite.utils.install import _server_config

    mock_server_resolve.side_effect = OSError("disk full")

    with pytest.raises(InstallError, match="disk full"):
        _server_config(
            _make_infra_config(), "Admin", "admin@example.com", "Sup3r$ecret!", False, **_server_config_kwargs()
        )


@mock.patch("deepfellow.suite.utils.install.server_apply")
@mock.patch("deepfellow.suite.utils.install.ensure_directory")
def test_server_install_apply_ensures_directory_then_applies(
    mock_ensure_directory: Mock, mock_server_apply: Mock
) -> None:
    from deepfellow.suite.utils.install import _server_install_apply

    config = _make_server_config()

    _server_install_apply(config)

    assert mock_ensure_directory.call_args == mock.call(config.directory, force_install=True)
    assert mock_server_apply.call_args == mock.call(config, will_auto_start=True)


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.start_server")
def test_server_start_wraps_docker_network_error(mock_start_server: Mock, mock_echo: Mock) -> None:
    """@translate_to_install_error generic-izes the re-raised typer.Exit's message (matching
    server install()'s own pre-existing behavior for this exact code path) - the specific reason is
    only surfaced as a console side effect via echo.error, not embedded in the raised exception."""
    from deepfellow.common.exceptions import DockerNetworkError
    from deepfellow.suite.utils.install import _server_start

    mock_start_server.side_effect = DockerNetworkError("no network")

    with pytest.raises(InstallError, match="Installation failed"):
        _server_start(DF_SERVER_DIRECTORY)

    assert mock_echo.error.call_args == mock.call("Failed to start server: no network")


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.start_server")
def test_server_start_reraises_original_error_in_debug_mode(mock_start_server: Mock, mock_echo: Mock) -> None:
    """Matches server install()'s own start_server error handling: --debug surfaces the specific
    DockerNetworkError message via InstallError, instead of the generic "Installation failed" one
    @translate_to_install_error substitutes for a bare typer.Exit (see the non-debug counterpart,
    test_server_start_wraps_docker_network_error)."""
    from deepfellow.common.exceptions import DockerNetworkError
    from deepfellow.suite.utils.install import _server_start

    state.debug = True
    mock_start_server.side_effect = DockerNetworkError("no network")

    with pytest.raises(InstallError, match="no network"):
        _server_start(DF_SERVER_DIRECTORY)


_SERVER_CREATE_ADMIN_ACTION: PostStartAction = _SERVER_WORKSPACE_POST_START_ACTIONS[0]


@mock.patch("deepfellow.suite.utils.install.create_admin_util")
def test_server_post_start_action_create_admin_calls_create_admin_util(mock_create_admin_util: Mock) -> None:
    from deepfellow.suite.utils.install import _server_post_start_action

    mock_create_admin_util.return_value = True

    _server_post_start_action(
        _SERVER_CREATE_ADMIN_ACTION, DF_SERVER_DIRECTORY, "Admin", "admin@example.com", "Sup3r$ecret!", False
    )

    assert mock_create_admin_util.call_count == 1
    assert mock_create_admin_util.call_args.kwargs["name"] == "Admin"
    assert mock_create_admin_util.call_args.kwargs["email"] == "admin@example.com"
    assert mock_create_admin_util.call_args.kwargs["password"] == "Sup3r$ecret!"
    assert mock_create_admin_util.call_args.kwargs["directory"] == DF_SERVER_DIRECTORY


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.create_admin_util")
def test_server_post_start_action_create_admin_warns_when_override_ignored_by_existing_account(
    mock_create_admin_util: Mock, mock_echo: Mock
) -> None:
    """An explicit --admin-* override that turns out to target an already-existing admin is
    silently discarded by create_admin_util (it only ever creates or no-ops) - must be surfaced."""
    from deepfellow.suite.utils.install import _server_post_start_action

    mock_create_admin_util.return_value = False  # already existed, no-op

    _server_post_start_action(
        _SERVER_CREATE_ADMIN_ACTION, DF_SERVER_DIRECTORY, "Bobby", "admin@example.com", "Sup3r$ecret!", True
    )

    assert mock_echo.warning.call_count == 1
    assert "admin@example.com" in mock_echo.warning.call_args.args[0]


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.create_admin_util")
def test_server_post_start_action_create_admin_no_warning_when_not_overridden(
    mock_create_admin_util: Mock, mock_echo: Mock
) -> None:
    """A prior run's persisted admin (not an explicit override this run) hitting the same
    already-exists no-op is expected, not a mistake - no warning."""
    from deepfellow.suite.utils.install import _server_post_start_action

    mock_create_admin_util.return_value = False  # already existed, no-op

    _server_post_start_action(
        _SERVER_CREATE_ADMIN_ACTION, DF_SERVER_DIRECTORY, "Admin", "admin@example.com", "Sup3r$ecret!", False
    )

    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.create_admin_util")
def test_server_post_start_action_create_admin_no_warning_when_override_created_fresh(
    mock_create_admin_util: Mock, mock_echo: Mock
) -> None:
    """An override that actually applies (no pre-existing account for that email) is not a
    silently-discarded change - no warning."""
    from deepfellow.suite.utils.install import _server_post_start_action

    mock_create_admin_util.return_value = True  # newly created

    _server_post_start_action(
        _SERVER_CREATE_ADMIN_ACTION, DF_SERVER_DIRECTORY, "Bobby", "bobby@example.com", "Sup3r$ecret!", True
    )

    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.suite.utils.install.server_dispatch_post_start_action")
@mock.patch("deepfellow.suite.utils.install.create_admin_util")
def test_server_post_start_action_dispatches_a_non_admin_action_unmodified(
    mock_create_admin_util: Mock, mock_dispatch: Mock
) -> None:
    """The DFCLI-14 follow-up guarantee: a server template's post-start action other than
    server.create_admin must actually be dispatched (via server's own dispatch mechanism, exactly
    as `server install --template` itself would run it), not silently dropped - and must never go
    through the admin-credential override path, which is scoped to server.create_admin only."""
    from deepfellow.suite.utils.install import _server_post_start_action

    other_action: PostStartAction = {"function": "server.some_other_action", "kwargs": {"foo": "bar"}}

    _server_post_start_action(other_action, DF_SERVER_DIRECTORY, "Admin", "admin@example.com", "Sup3r$ecret!", False)

    assert mock_dispatch.call_count == 1
    assert mock_dispatch.call_args == mock.call(other_action)
    assert mock_create_admin_util.call_count == 0


def test_validate_template_accepts_a_known_builtin_name() -> None:
    _validate_template("workspace")


def test_validate_template_raises_on_unknown_name() -> None:
    with pytest.raises(InstallError, match="not a valid suite install template"):
        _validate_template("nonexistent")


def test_resolve_effective_template_adopts_given_template_for_a_fresh_state() -> None:
    """A freshly-started install_state (no persisted template yet) simply records this
    invocation's own --template, with nothing to warn about."""
    install_state = SuiteInstallState()

    result = _resolve_effective_template(install_state, "workspace")

    assert result == "workspace"
    assert install_state.template == "workspace"


@mock.patch("deepfellow.suite.utils.install.echo")
def test_resolve_effective_template_reuses_matching_persisted_template_without_warning(mock_echo: Mock) -> None:
    install_state = SuiteInstallState(template="workspace")

    result = _resolve_effective_template(install_state, "workspace")

    assert result == "workspace"
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.suite.utils.install.echo")
def test_resolve_effective_template_warns_and_reuses_persisted_template_on_mismatch(mock_echo: Mock) -> None:
    """The core DFCLI-14 follow-up guarantee: a persisted template from a run being continued
    always wins over this invocation's own --template - which would otherwise silently mix one
    template's infra/server configuration with another template's installed services/models."""
    install_state = SuiteInstallState(template="workspace")

    result = _resolve_effective_template(install_state, "other")

    assert result == "workspace"
    assert install_state.template == "workspace"
    assert mock_echo.warning.call_count == 1
    message = mock_echo.warning.call_args.args[0]
    assert "'other'" in message
    assert "'workspace'" in message


@mock.patch("deepfellow.suite.utils.install.assert_docker")
def test_install_raises_before_docker_check_when_template_is_unknown(mock_assert_docker: Mock) -> None:
    with pytest.raises(InstallError, match="not a valid suite install template"):
        install(template="nonexistent")

    assert mock_assert_docker.call_count == 0


@mock.patch("deepfellow.suite.utils.install.assert_docker")
def test_install_raises_before_docker_check_when_template_is_a_file_path(mock_assert_docker: Mock) -> None:
    with pytest.raises(InstallError, match="not a valid suite install template"):
        install(template="/tmp/custom.yaml")

    assert mock_assert_docker.call_count == 0


_FAKE_TWO_ACTION_TEMPLATE: InstallTemplate = {
    "config": {},
    "post_start_actions": [
        {"function": "infra.service.install", "kwargs": {"name": "vllm", "spec": "{}"}},
        {"function": "infra.model.install", "kwargs": {"service_name": "vllm", "model_name": "custom-model"}},
    ],
}


@mock.patch("deepfellow.suite.utils.install.infra_resolve_template")
@_patch_all_steps
def test_install_derives_post_start_action_steps_and_granted_models_from_template(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_infra_resolve_template: Mock,
) -> None:
    mock_infra_resolve_template.return_value = _FAKE_TWO_ACTION_TEMPLATE
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    workspace = _make_workspace()
    mock_create_workspace.return_value = workspace

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_infra_post_start_action.call_count == 2
    assert mock_infra_post_start_action.call_args_list == [
        mock.call(action, DF_INFRA_DIRECTORY, False) for action in _FAKE_TWO_ACTION_TEMPLATE["post_start_actions"]
    ]
    assert mock_update_project.call_args.args[2:] == (
        workspace.organization.id,
        workspace.project.id,
        {"models": ["custom-model"]},
    )


@mock.patch("deepfellow.suite.utils.install.server_resolve_template")
@mock.patch("deepfellow.suite.utils.install.infra_resolve_template")
@mock.patch("deepfellow.suite.utils.install._SUITE_BUILTIN_TEMPLATES", frozenset({"workspace", "other"}))
@_patch_all_steps
def test_install_resume_with_different_template_warns_and_reuses_persisted_one(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_infra_resolve_template: Mock,
    mock_server_resolve_template: Mock,
) -> None:
    """The core review-finding guarantee: --resume with a --template different from (or simply
    omitting, defaulting back to "workspace") the one the previous run persisted must not silently
    mix the two - infra/server stay configured for the persisted template, and the services/models
    this run installs and grants access to must come from that SAME persisted template, not this
    invocation's --template.

    "other" isn't a real built-in template (only "workspace" is, in production) - only
    `_SUITE_BUILTIN_TEMPLATES` is patched to accept it as a name for this test, so
    `infra_resolve_template()`/`server_resolve_template()` are stubbed to resolve it to some other
    (fake) template's actions, distinguishable from "workspace"'s real ones.
    """
    mock_infra_resolve_template.side_effect = lambda name: (
        INFRA_BUILTIN_TEMPLATES["workspace"] if name == "workspace" else _FAKE_TWO_ACTION_TEMPLATE
    )
    mock_server_resolve_template.side_effect = lambda name: (
        SERVER_BUILTIN_TEMPLATES["workspace"] if name == "workspace" else _FAKE_TWO_ACTION_TEMPLATE
    )
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_config", "server_config"], template="workspace"
    )
    mock_get_token_from_login.return_value = "token"
    workspace = _make_workspace()
    mock_create_workspace.return_value = workspace

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        resume=True,
        template="other",
    )

    warning_messages = [call.args[0] for call in mock_echo.warning.call_args_list]
    assert any("'other'" in msg and "'workspace'" in msg for msg in warning_messages)
    # The persisted "workspace" template's real post-start actions/models were used - not "other"'s.
    assert mock_infra_post_start_action.call_args_list == [
        mock.call(action, DF_INFRA_DIRECTORY, True) for action in _WORKSPACE_POST_START_ACTIONS
    ]
    assert mock_server_post_start_action.call_args_list == [
        mock.call(action, DF_SERVER_DIRECTORY, "Admin", "admin@example.com", "Sup3r$ecret!", True)
        for action in _SERVER_WORKSPACE_POST_START_ACTIONS
    ]
    assert mock_update_project.call_args.args[2:] == (
        workspace.organization.id,
        workspace.project.id,
        {"models": ["gemma4:e4b", "mxbai-embed-large", "qwen3.5:4b"]},
    )
    assert mock_save_state.call_args.args[0].template == "workspace"


@_patch_all_steps
def test_install_resume_ignores_leftover_old_post_start_action_step_ids(
    mock_server_config_to_dict: Mock,
    mock_server_config_from_dict: Mock,
    mock_server_config: Mock,
    mock_infra_config_to_dict: Mock,
    mock_infra_config_from_dict: Mock,
    mock_infra_config: Mock,
    mock_install_directory_intact: Mock,
    mock_is_service_running: Mock,
    mock_assert_docker: Mock,
    mock_load_state: Mock,
    mock_save_state: Mock,
    mock_delete_state: Mock,
    mock_update_project: Mock,
    mock_create_workspace: Mock,
    mock_get_token_from_login: Mock,
    mock_set_default_server_directory: Mock,
    mock_server_post_start_action: Mock,
    mock_server_start: Mock,
    mock_server_install_apply: Mock,
    mock_infra_post_start_action: Mock,
    mock_infra_start: Mock,
    mock_infra_install_apply: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """Old, pre-template-flag fixed step ids never match a newly-computed infra_post_start_action_{i}
    id, so all 4 actions simply re-run once - harmless, since each is proven idempotent (always_run)."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=[
            "infra_config",
            "server_config",
            "infra_install",
            "infra_start",
            "infra_service_install",
            "infra_model_install_chat",
            "infra_model_install_embedding",
            "infra_model_install_fast",
        ]
    )
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_post_start_action.call_count == 4
