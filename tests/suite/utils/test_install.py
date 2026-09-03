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
from deepfellow.server.organization.utils import Organization
from deepfellow.server.project.api_key.utils import ApiKey
from deepfellow.server.project.utils import Project
from deepfellow.server.utils.workspace import Workspace
from deepfellow.suite.utils.install import STEPS, TOTAL_STEPS, _install_directory_intact, _workspace_to_dict, install
from deepfellow.suite.utils.state import SuiteInstallState


def _default_infra_install_apply_call(*, force_install: bool = False) -> mock._Call:
    return mock.call(
        force_install,
        port=DF_INFRA_PORT,
        image=DF_INFRA_IMAGE,
        local_image=False,
        directory=DF_INFRA_DIRECTORY,
        docker_config=None,
        storage=DF_INFRA_STORAGE_DIR,
        docker_network=DF_INFRA_DOCKER_NETWORK,
        explicitly_provided=set(),
    )


def _default_server_install_apply_call(
    *,
    force_install: bool = False,
    name: str = "Admin",
    email: str = "admin@example.com",
    password: str = "Sup3r$ecret!",
) -> mock._Call:
    return mock.call(
        name,
        email,
        password,
        force_install,
        infra_directory=DF_INFRA_DIRECTORY,
        port=DF_SERVER_PORT,
        image=DF_SERVER_IMAGE,
        local_image=False,
        directory=DF_SERVER_DIRECTORY,
        docker_network=DF_INFRA_DOCKER_NETWORK,
        mongodb_port=DF_MONGO_PORT,
        mongodb_username="",
        mongodb_password="",
        falkordb_active=False,
        falkordb_url=DF_FALKORDB_URL,
        falkordb_username="",
        falkordb_password="",
        otel_local=False,
        explicitly_provided=set(),
    )


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
    behavior unchanged. `env_get` is appended last purely so every existing signature only needs one
    new trailing parameter, since install() calls it exactly once itself (to resolve the
    actually-configured DF_SERVER_PORT) - independent of whichever step functions a test overrides.
    """
    for target in (
        "deepfellow.suite.utils.install._infra_install_apply",
        "deepfellow.suite.utils.install._infra_start",
        "deepfellow.suite.utils.install._infra_service_install",
        "deepfellow.suite.utils.install._infra_model_install",
        "deepfellow.suite.utils.install._server_install_apply",
        "deepfellow.suite.utils.install._server_start",
        "deepfellow.suite.utils.install._server_create_admin",
        "deepfellow.suite.utils.install.set_default_server_directory",
        "deepfellow.suite.utils.install.get_token_from_login",
        "deepfellow.suite.utils.install.create_workspace",
        "deepfellow.suite.utils.install.update_project",
        "deepfellow.suite.utils.install.delete_state",
        "deepfellow.suite.utils.install.save_state",
        "deepfellow.suite.utils.install.load_state",
        "deepfellow.suite.utils.install.assert_docker",
    ):
        func = mock.patch(target)(func)
    for target in (
        "deepfellow.suite.utils.install.is_service_running",
        "deepfellow.suite.utils.install._install_directory_intact",
    ):
        func = mock.patch(target, return_value=True)(func)
    func = mock.patch("deepfellow.suite.utils.install.echo")(func)
    return mock.patch("deepfellow.suite.utils.install.env_get")(func)


@_patch_all_steps
def test_install_success_calls_all_steps_in_order(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    workspace = _make_workspace()
    mock_create_workspace.return_value = workspace

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_infra_install_apply.call_count == 1
    assert mock_infra_install_apply.call_args == _default_infra_install_apply_call()
    assert mock_infra_start.call_count == 1
    assert mock_infra_service_install.call_count == 1
    # Fresh (non --resume) run: "Updated config/secrets" stays visible - only --resume quiets it.
    assert mock_infra_service_install.call_args == mock.call(DF_INFRA_DIRECTORY, False)
    assert mock_infra_model_install.call_count == 3
    assert mock_infra_model_install.call_args_list == [
        mock.call("gemma4:e4b", DF_INFRA_DIRECTORY, False),
        mock.call("mxbai-embed-large", DF_INFRA_DIRECTORY, False),
        mock.call("qwen3.5:4b", DF_INFRA_DIRECTORY, False),
    ]
    assert mock_server_install_apply.call_count == 1
    assert mock_server_install_apply.call_args == _default_server_install_apply_call()
    assert mock_server_start.call_count == 1
    assert mock_server_create_admin.call_count == 1
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
def test_install_stops_after_infra_install_error_and_does_not_delete_state(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """Even though infra_install itself never succeeds, the resolved admin credentials must still be
    persisted immediately - otherwise a step that keeps failing (e.g. the user repeatedly declining
    infra install's own directory-exists confirmation) would force retyping them on every retry."""
    mock_load_state.return_value = None
    mock_infra_install_apply.side_effect = InstallError("boom")

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_infra_start.call_count == 0
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
def test_install_stops_after_infra_start_error_does_not_call_service_install(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """infra install (config/apply) can succeed while infra start fails independently - this must
    surface as its own distinct step, not get lumped into "infra install"."""
    mock_load_state.return_value = None
    mock_infra_start.side_effect = typer.Exit(1)

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_infra_install_apply.call_count == 1
    assert mock_infra_service_install.call_count == 0
    assert mock_server_install_apply.call_count == 0
    # +1: admin credentials are written immediately once resolved, before infra_install ever runs.
    assert mock_save_state.call_count == 2
    assert mock_save_state.call_args.args[0].completed_steps == ["infra_install"]


@_patch_all_steps
def test_install_stops_when_server_install_raises_does_not_call_login(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_server_install_apply.side_effect = InstallError("DF_INFRA_API_KEY not found")

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_server_start.call_count == 0
    assert mock_get_token_from_login.call_count == 0
    assert mock_delete_state.call_count == 0


@_patch_all_steps
def test_install_bare_rerun_with_existing_state_starts_fresh(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A bare rerun (no --resume) over an unfinished previous run's state must not error out asking
    for --resume - once the user confirms discarding it, it runs a normal, complete fresh install,
    overwriting the state file up front instead of requiring the user to delete it by hand."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_install", "infra_start"],
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
    assert mock_infra_install_apply.call_args == _default_infra_install_apply_call()
    assert mock_infra_start.call_count == 1
    assert mock_server_install_apply.call_args == _default_server_install_apply_call()
    # The stale state is overwritten immediately, before any step runs - not just lazily on the
    # first step's own save_state() call - so a crash before step 1 completes doesn't leave the OLD
    # run's progress (and stale admin) on disk. The new admin is then written immediately too, right
    # after resolving it, so it's never lost to a step that fails.
    assert saved_snapshots[0] == ([], None)
    assert saved_snapshots[1] == ([], {"name": "Admin", "email": "admin@example.com", "password": "Sup3r$ecret!"})
    assert mock_save_state.call_count == TOTAL_STEPS + 2


@_patch_all_steps
def test_install_bare_rerun_confirm_message_mentions_api_key_when_workspace_exists(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
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
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A prior run that never reached workspace creation has nothing irrecoverable to lose - the
    confirmation message shouldn't falsely warn about an API key that was never created."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_install"])
    mock_echo.confirm.return_value = True
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=False)

    message = mock_echo.confirm.call_args.args[0]
    assert "API key" not in message


@_patch_all_steps
def test_install_bare_rerun_declining_discard_continues_previous_install(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """Declining the discard confirmation must not error out or require a second invocation with
    --resume - it just continues the previous run in place, exactly as --resume would."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_install", "infra_start"],
        admin={"name": "Persisted Admin", "email": "persisted@example.com", "password": "Pers1sted$ecret!"},
    )
    mock_echo.confirm.return_value = False
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name=None, admin_email=None, admin_password=None, resume=False)

    assert mock_infra_install_apply.call_count == 0
    assert mock_infra_start.call_count == 0
    assert mock_server_install_apply.call_args == _default_server_install_apply_call(
        name="Persisted Admin", email="persisted@example.com", password="Pers1sted$ecret!"
    )
    # Continuing here behaves exactly as --resume would (per this test's own docstring), so the
    # ollama service/model install calls must be quieted the same way a real --resume run's are -
    # not left noisy just because the local `resume` flag itself was never passed.
    assert mock_infra_service_install.call_args == mock.call(DF_INFRA_DIRECTORY, True)
    assert any(call == mock.call("Continuing the previous install instead.") for call in mock_echo.info.call_args_list)
    # No "state discarded" warning (nothing was discarded) - just the unconditional plaintext-
    # password notice that fires once per invocation, regardless of whether credentials were
    # freshly prompted or reused as-is from persisted state.
    assert mock_echo.warning.call_args_list == [
        mock.call(
            "The admin password is being saved in plain text to "
            f"{DF_SUITE_INSTALL_STATE_FILE}, so `--resume` can reuse it without re-prompting. "
            "It's removed automatically once this install fully succeeds - if you abandon this "
            "run, remove it yourself."
        )
    ]


@_patch_all_steps
def test_install_bare_rerun_with_yes_flag_skips_confirmation_and_discards(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """--yes must skip the confirmation entirely (for scripted/CI use) and go straight to
    discarding the previous state, same as answering "yes" interactively."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_install", "infra_start"])
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()
    state.yes = True

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=False)

    assert mock_echo.confirm.call_count == 0
    assert mock_infra_install_apply.call_count == 1
    assert mock.call("Previous suite install state discarded; starting fresh.") in mock_echo.warning.call_args_list


@_patch_all_steps
def test_install_resume_skips_already_completed_steps_still_live(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """infra_install/infra_start skip because their live checks confirm the directory/container are
    still there (both mocks default to True via _patch_all_steps) - the live-state fix.
    infra_service_install/infra_model_install/server_create_admin always re-run regardless of
    completed_steps, relying on their own already-installed/already-exists idempotency."""
    completed = [
        "infra_install",
        "infra_start",
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

    assert mock_infra_install_apply.call_count == 0
    assert mock_infra_start.call_count == 0
    assert mock_infra_service_install.call_count == 1
    # A --resume run repeats these calls (once per model) against the exact same, already-confirmed
    # connection - "Updated config/secrets" would just be noise, so it's quieted here.
    assert mock_infra_service_install.call_args == mock.call(DF_INFRA_DIRECTORY, True)
    assert mock_infra_model_install.call_count == 3
    assert mock_infra_model_install.call_args_list == [
        mock.call("gemma4:e4b", DF_INFRA_DIRECTORY, True),
        mock.call("mxbai-embed-large", DF_INFRA_DIRECTORY, True),
        mock.call("qwen3.5:4b", DF_INFRA_DIRECTORY, True),
    ]
    assert mock_server_install_apply.call_count == 1
    assert mock_server_start.call_count == 1
    assert mock_server_create_admin.call_count == 1


@_patch_all_steps
def test_install_infra_start_reruns_when_container_no_longer_running_despite_completed_steps(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A container removed after infra_start succeeded (e.g. `docker rm`) must be detected live and
    restarted, not silently trusted as still up just because the step id is in completed_steps."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_install", "infra_start"])
    mock_install_directory_intact.return_value = True
    mock_is_service_running.return_value = False
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 0
    assert mock_infra_start.call_count == 1
    assert mock_is_service_running.call_args_list[0] == mock.call("infra", cwd=DF_INFRA_DIRECTORY)
    assert mock_infra_service_install.call_count == 1
    warning_messages = [call.args[0] for call in mock_echo.warning.call_args_list]
    assert (
        "Step 2/12: infra start... was marked complete previously, but is no longer detected as up; "
        "re-running." in warning_messages
    )


@_patch_all_steps
def test_install_infra_install_reruns_when_directory_missing_despite_completed_steps(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A fully deleted infra directory (e.g. `rm -rf ~/.deepfellow/infra`) must be detected live and
    reprovisioned, not silently trusted as still installed - the exact bug this fix resolves."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_install"])
    mock_install_directory_intact.return_value = False
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 1
    assert mock_infra_install_apply.call_args == _default_infra_install_apply_call(force_install=True)
    warning_messages = [call.args[0] for call in mock_echo.warning.call_args_list]
    assert (
        "Step 1/12: infra install... was marked complete previously, but is no longer detected as up; "
        "re-running." in warning_messages
    )


@_patch_all_steps
def test_install_infra_start_reruns_when_infra_self_heals_despite_container_still_running(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A deleted-then-reprovisioned infra directory (`rm -rf`'d without stopping the container)
    mints a brand-new DF_INFRA_API_KEY, but the old container - never actually stopped - still
    reports as running. infra_start must restart it to load the fresh key instead of trusting
    is_service_running alone, exactly like server_install/server_start already do when infra
    self-heals."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_install", "infra_start"])
    mock_install_directory_intact.return_value = False
    mock_is_service_running.return_value = True
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 1
    assert mock_infra_install_apply.call_args == _default_infra_install_apply_call(force_install=True)
    assert mock_infra_start.call_count == 1


@_patch_all_steps
def test_install_server_start_reruns_when_container_no_longer_running_despite_completed_steps(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    completed_through_server_start = [
        step_id for step_id, _ in STEPS if step_id not in ("server_create_admin", "server_login")
    ][:8]
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
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    completed_through_server_install = [
        step_id for step_id, _ in STEPS if step_id not in ("server_start", "server_create_admin", "server_login")
    ][:7]
    mock_load_state.return_value = SuiteInstallState(completed_steps=completed_through_server_install)
    mock_install_directory_intact.side_effect = lambda directory: directory != DF_SERVER_DIRECTORY
    mock_is_service_running.return_value = True
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 0
    assert mock_server_install_apply.call_count == 1
    assert mock_server_install_apply.call_args == _default_server_install_apply_call(force_install=True)


@_patch_all_steps
def test_install_server_reruns_install_and_start_when_infra_self_heals_despite_server_directory_intact(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A self-healed infra directory (rm -rf'd, then reprovisioned) mints a brand-new
    DF_INFRA_API_KEY - configure_uuid_key() only reuses an existing one when the directory it
    reads from is still there. The server's own directory being perfectly intact must not be
    treated as "nothing to do": server install must re-apply its config to pick up the fresh key,
    and server start must actually restart the container to load it - a running container never
    picks up an .env change on its own. Without this, the server is silently left pointed at a
    dead key - exactly the "misleading connection error instead of self-healing" bug this whole
    live-state design exists to prevent."""
    completed_through_server_start = [
        step_id for step_id, _ in STEPS if step_id not in ("server_create_admin", "server_login")
    ][:8]
    mock_load_state.return_value = SuiteInstallState(completed_steps=completed_through_server_start)
    mock_install_directory_intact.side_effect = lambda directory: directory != DF_INFRA_DIRECTORY
    mock_is_service_running.return_value = True
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 1
    assert mock_server_install_apply.call_count == 1
    assert mock_server_install_apply.call_args == _default_server_install_apply_call(force_install=True)
    assert mock_server_start.call_count == 1


@_patch_all_steps
def test_install_create_admin_always_executes_even_when_completed(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """create_admin is not cheaply live-checkable (an admin is a DB record, not a docker service) -
    it must always re-attempt, relying on create_admin_util's own idempotency for an existing admin."""
    completed_through_create_admin = [step_id for step_id, _ in STEPS if step_id not in ("server_login",)][:9]
    mock_load_state.return_value = SuiteInstallState(completed_steps=completed_through_create_admin)
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_server_create_admin.call_count == 1


@_patch_all_steps
def test_install_grant_model_access_always_executes_even_when_completed(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
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
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A crash mid infra-install (directory/.env partially written) means step 1 itself is not
    marked complete yet. --force-install is the single source of truth for both apply calls - a
    bare --resume, regardless of completed_steps content, must never implicitly force one on."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=[])
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_args == _default_infra_install_apply_call()
    assert mock_server_install_apply.call_args == _default_server_install_apply_call()


@_patch_all_steps
def test_install_resume_with_partial_completed_steps_does_not_force(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """Same as above, with infra_install already completed (and still verified intact, so it's
    skipped outright) - server_install must still default to force_install=False, not inherit
    force from infra_install having succeeded."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_install"])
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 0
    assert mock_server_install_apply.call_args == _default_server_install_apply_call()


@_patch_all_steps
def test_install_force_install_flag_is_passed_to_infra_and_server_apply(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """--force-install is the single source of truth for both infra and server install's
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

    assert mock_infra_install_apply.call_args == _default_infra_install_apply_call(force_install=True)
    assert mock_server_install_apply.call_args == _default_server_install_apply_call(force_install=True)


@_patch_all_steps
def test_install_resume_with_no_state_file_runs_fresh(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_infra_install_apply.call_count == 1
    assert mock_infra_install_apply.call_args == _default_infra_install_apply_call()
    assert mock_server_install_apply.call_args == _default_server_install_apply_call()


@_patch_all_steps
def test_install_resume_reuses_persisted_workspace_without_recreating(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
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


@_patch_all_steps
def test_install_resume_with_corrupted_persisted_workspace_fails_cleanly(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
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
def test_install_resume_reuses_persisted_admin_without_prompting(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A `--resume` run must reuse the admin credentials a prior run already collected (whether
    typed interactively or passed via --admin-*/env vars) instead of prompting for them again."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_install"],
        admin={"name": "Persisted Admin", "email": "persisted@example.com", "password": "Pers1sted$ecret!"},
    )
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name=None, admin_email=None, admin_password=None, resume=True)

    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_server_install_apply.call_args == _default_server_install_apply_call(
        name="Persisted Admin", email="persisted@example.com", password="Pers1sted$ecret!"
    )
    assert mock_get_token_from_login.call_args.kwargs["email"] == "persisted@example.com"
    assert mock_get_token_from_login.call_args.kwargs["password"] == "Pers1sted$ecret!"
    # A pure passthrough of the persisted value - no flag, no prompt - must not count as an
    # override: _server_create_admin() would otherwise warn about a no-op that was actually
    # expected (the same admin as before, not a value the user just supplied this run).
    assert mock_server_create_admin.call_args == mock.call(
        "Persisted Admin", "persisted@example.com", "Pers1sted$ecret!", DF_SERVER_DIRECTORY, False
    )


@_patch_all_steps
def test_install_resume_admin_flag_overrides_persisted_credentials(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """An explicit --admin-password (or --admin-name/--admin-email) on the resuming invocation must
    win over whatever a prior run persisted, same as it wins over any other fallback source."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_install"],
        admin={"name": "Persisted Admin", "email": "persisted@example.com", "password": "Pers1sted$ecret!"},
    )
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name=None, admin_email=None, admin_password="N3w$ecret!", resume=True)

    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_server_install_apply.call_args == _default_server_install_apply_call(
        name="Persisted Admin", email="persisted@example.com", password="N3w$ecret!"
    )
    assert mock_save_state.call_args_list[0].args[0].admin == {
        "name": "Persisted Admin",
        "email": "persisted@example.com",
        "password": "N3w$ecret!",
    }


@_patch_all_steps
def test_install_non_interactive_resume_uses_persisted_admin_without_error(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """--non-interactive must not require --admin-* on a `--resume` run once a prior run already
    persisted them - only a genuinely missing value (covered by the existing "missing" test) should
    raise."""
    mock_load_state.return_value = SuiteInstallState(
        completed_steps=["infra_install"],
        admin={"name": "Persisted Admin", "email": "persisted@example.com", "password": "Pers1sted$ecret!"},
    )
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()
    state.non_interactive = True

    install(admin_name=None, admin_email=None, admin_password=None, resume=True)

    assert mock_server_install_apply.call_args == _default_server_install_apply_call(
        name="Persisted Admin", email="persisted@example.com", password="Pers1sted$ecret!"
    )


@_patch_all_steps
def test_install_persists_resolved_admin_credentials_on_fresh_run(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
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
def test_install_warns_about_plaintext_password_exactly_once(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """The plaintext-password notice must fire exactly once per invocation, at the single point
    where admin credentials get persisted - not on every one of the ~12 subsequent save_state()
    calls that just persist step progress."""
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    plaintext_warnings = [call for call in mock_echo.warning.call_args_list if "plain text" in call.args[0]]
    assert len(plaintext_warnings) == 1
    assert str(DF_SUITE_INSTALL_STATE_FILE) in plaintext_warnings[0].args[0]
    assert mock_save_state.call_count > 1


@_patch_all_steps
def test_install_resumed_create_admin_step_succeeds_and_continues(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """create_admin is now idempotent (see server/utils/users.py) - a resumed run whose admin
    already existed from before the interruption must succeed, not abort."""
    completed_through_server_start = [
        step_id for step_id, _ in STEPS if step_id not in ("server_create_admin", "server_login")
    ][:8]
    mock_load_state.return_value = SuiteInstallState(completed_steps=completed_through_server_start)
    mock_server_create_admin.return_value = None  # idempotent no-op, not an error
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", resume=True)

    assert mock_server_create_admin.call_count == 1
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
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
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
def test_install_prompted_credentials_are_reused_for_server_install_and_login(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_echo.prompt_until_valid.side_effect = ["Prompted Admin", "prompted@example.com", "Pr0mpted$ecret!"]
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name=None, admin_email=None, admin_password=None)

    assert mock_server_install_apply.call_args == _default_server_install_apply_call(
        name="Prompted Admin", email="prompted@example.com", password="Pr0mpted$ecret!"
    )
    assert mock_get_token_from_login.call_args.kwargs["email"] == "prompted@example.com"
    assert mock_get_token_from_login.call_args.kwargs["password"] == "Pr0mpted$ecret!"
    # Typed at a prompt is just as deliberate as an explicit --admin-* flag: the user is
    # supplying an admin identity for this run, not passively reusing a persisted one, so it
    # must count as an override too - otherwise a value that turns out to target an
    # already-existing account gets silently discarded with no warning (see the concrete failure
    # scenario in the !311 review: a mistyped password at this exact prompt led to a confusing,
    # unrelated login failure two steps later instead of a clear warning here).
    assert mock_server_create_admin.call_args == mock.call(
        "Prompted Admin", "prompted@example.com", "Pr0mpted$ecret!", DF_SERVER_DIRECTORY, True
    )


@_patch_all_steps
def test_install_checks_docker_before_prompting(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
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
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
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

    assert mock_infra_install_apply.call_args.kwargs["port"] == 9000
    assert mock_server_install_apply.call_args.kwargs["port"] == 9001
    # server_url used for login/workspace-creation must follow the actually-resolved server port.
    assert mock_get_token_from_login.call_args.args[1] == "http://localhost:9001"


@_patch_all_steps
def test_install_uses_resolved_server_port_over_cli_value_for_login_url(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """If server install resolves a different port than the raw CLI value - e.g. restored from a
    prior install's own .env because --server-port wasn't passed this time - server_url must follow
    the actually-resolved port (read back via env_get), not the value install() was called with, or
    login/workspace-creation would target a server that isn't listening there."""
    mock_load_state.return_value = None
    mock_env_get.return_value = "9002"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_server_install_apply.call_args.kwargs["port"] == DF_SERVER_PORT
    assert mock_get_token_from_login.call_args.args[1] == "http://localhost:9002"


@_patch_all_steps
def test_install_forwards_docker_network_to_both_infra_and_server_install(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
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

    assert mock_infra_install_apply.call_args.kwargs["docker_network"] == "my-custom-net"
    assert mock_server_install_apply.call_args.kwargs["docker_network"] == "my-custom-net"


@_patch_all_steps
def test_install_forwards_falkordb_options_to_server_install(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
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

    assert mock_server_install_apply.call_args.kwargs["falkordb_active"] is True
    assert mock_server_install_apply.call_args.kwargs["falkordb_url"] == "my-falkordb:6379"
    assert mock_server_install_apply.call_args.kwargs["falkordb_username"] == "graphuser"
    assert mock_server_install_apply.call_args.kwargs["falkordb_password"] == "graphpass"


@_patch_all_steps
def test_install_falkordb_disabled_by_default(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_server_install_apply.call_args.kwargs["falkordb_active"] is False


@_patch_all_steps
def test_install_forwards_mongodb_port_and_credentials_to_server_install(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
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

    assert mock_server_install_apply.call_args.kwargs["mongodb_port"] == 27018
    assert mock_server_install_apply.call_args.kwargs["mongodb_username"] == "dfuser"
    assert mock_server_install_apply.call_args.kwargs["mongodb_password"] == "dfpass"


@_patch_all_steps
def test_install_forwards_otel_local_to_server_install(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    mock_load_state.return_value = None
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = _make_workspace()

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", otel_local=True)

    assert mock_server_install_apply.call_args.kwargs["otel_local"] is True


@_patch_all_steps
def test_install_forwards_custom_infra_and_server_directories(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """A custom --infra-directory/--server-directory must be reflected in the decomposed steps
    that operate against those specific directories (install apply, start, create-admin, service
    and model install), and a custom server directory must be forwarded to
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

    assert mock_infra_install_apply.call_args.kwargs["directory"] == custom_infra_directory
    assert mock_infra_start.call_args == mock.call(custom_infra_directory)
    assert mock_infra_service_install.call_args == mock.call(custom_infra_directory, False)
    assert mock_server_install_apply.call_args.kwargs["infra_directory"] == custom_infra_directory
    assert mock_server_install_apply.call_args.kwargs["directory"] == custom_server_directory
    assert mock_server_start.call_args == mock.call(custom_server_directory)
    assert mock_server_create_admin.call_args == mock.call(
        "Admin", "admin@example.com", "Sup3r$ecret!", custom_server_directory, True
    )
    assert mock_set_default_server_directory.call_args == mock.call(custom_server_directory, force=False)
    assert mock_env_get.call_args == mock.call(custom_server_directory / ".env", "DF_SERVER_PORT")


@_patch_all_steps
def test_install_maps_explicitly_provided_to_infra_and_server_port_only(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """explicitly_provided={"infra_port"} must reach only infra_install_apply's own "port" key,
    not server_install_apply's - the two ports are independent despite sharing the same target
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

    assert mock_infra_install_apply.call_args.kwargs["explicitly_provided"] == {"port"}
    assert mock_server_install_apply.call_args.kwargs["explicitly_provided"] == set()


@_patch_all_steps
def test_install_maps_explicitly_provided_docker_network_to_both(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
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

    assert mock_infra_install_apply.call_args.kwargs["explicitly_provided"] == {"docker_network"}
    assert mock_server_install_apply.call_args.kwargs["explicitly_provided"] == {"docker_network"}


@_patch_all_steps
def test_install_warns_when_infra_config_flags_ignored_because_step_skipped(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """--infra-port (etc.) passed on a --resume run against an already-installed infra must warn
    that it was ignored, mirroring _server_create_admin's admin_overridden warning - the step is
    skipped outright (is_done), so its config flags never reach infra_resolve()."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_install"])
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
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """Same as above, for one of server install's own config flags - not one of the 3 fields that
    also participate in template-merge precedence, to prove the warning isn't limited to those."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_install", "infra_start", "server_install"])
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
def test_install_no_warning_when_config_flags_used_because_step_reruns(
    mock_infra_install_apply: Mock,
    mock_infra_start: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install_apply: Mock,
    mock_server_start: Mock,
    mock_server_create_admin: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_delete_state: Mock,
    mock_save_state: Mock,
    mock_load_state: Mock,
    mock_assert_docker: Mock,
    mock_is_service_running: Mock,
    mock_install_directory_intact: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
) -> None:
    """When infra_install actually reruns (e.g. its directory went missing), explicitly-passed
    config flags DO take effect - no "ignored" warning fires alongside the "no longer detected as
    up; re-running" one."""
    mock_load_state.return_value = SuiteInstallState(completed_steps=["infra_install"])
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
    assert not any("was ignored" in msg for msg in warning_messages)


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


@mock.patch("deepfellow.suite.utils.install.infra_apply")
@mock.patch("deepfellow.suite.utils.install.infra_resolve")
@mock.patch("deepfellow.suite.utils.install.infra_inspect")
def test_infra_install_apply_uses_workspace_template_and_will_auto_start(
    mock_infra_inspect: Mock, mock_infra_resolve: Mock, mock_infra_apply: Mock
) -> None:
    from deepfellow.suite.utils.install import _infra_install_apply

    _infra_install_apply(
        force_install=True,
        port=DF_INFRA_PORT,
        image=DF_INFRA_IMAGE,
        local_image=False,
        directory=DF_INFRA_DIRECTORY,
        docker_config=None,
        storage=DF_INFRA_STORAGE_DIR,
        docker_network=DF_INFRA_DOCKER_NETWORK,
        explicitly_provided=set(),
    )

    assert mock_infra_inspect.call_args.kwargs["template"] == "workspace"
    assert mock_infra_inspect.call_args.kwargs["force_install"] is True
    assert mock_infra_resolve.call_args.args[0] == mock_infra_inspect.return_value
    assert mock_infra_resolve.call_args.kwargs["docker_config"] == DF_INFRA_DIRECTORY / "docker-config.json"
    assert mock_infra_apply.call_args == mock.call(mock_infra_resolve.return_value, will_auto_start=True)


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
def test_infra_service_install_dispatches_ollama_with_localhost_url(mock_dispatch: Mock, mock_env_get: Mock) -> None:
    from deepfellow.suite.utils.install import _infra_service_install

    mock_env_get.return_value = "9999"

    _infra_service_install(DF_INFRA_DIRECTORY, quiet=True)

    action = mock_dispatch.call_args.args[0]
    assert action["function"] == "infra.service.install"
    assert action["kwargs"]["name"] == "ollama"
    assert action["kwargs"]["server"] == "http://localhost:9999"
    assert action["kwargs"]["quiet"] is True


@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.infra_dispatch_post_start_action")
def test_infra_model_install_dispatches_model_action(mock_dispatch: Mock, mock_env_get: Mock) -> None:
    from deepfellow.suite.utils.install import _infra_model_install

    mock_env_get.return_value = None

    _infra_model_install("gemma4:e4b", DF_INFRA_DIRECTORY, quiet=False)

    action = mock_dispatch.call_args.args[0]
    assert action["function"] == "infra.model.install"
    assert action["kwargs"] == {
        "service_name": "ollama",
        "model_name": "gemma4:e4b",
        "server": mock.ANY,
        "quiet": False,
    }


def _server_install_apply_kwargs(**overrides: object) -> dict:
    base = {
        "infra_directory": DF_INFRA_DIRECTORY,
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
        "explicitly_provided": set(),
    }
    base.update(overrides)
    return base


@mock.patch("deepfellow.suite.utils.install.env_get")
def test_server_install_apply_raises_when_infra_api_key_missing(mock_env_get: Mock) -> None:
    from deepfellow.suite.utils.install import _server_install_apply

    mock_env_get.return_value = None

    with pytest.raises(InstallError, match="DF_INFRA_API_KEY not found"):
        _server_install_apply("Admin", "admin@example.com", "Sup3r$ecret!", False, **_server_install_apply_kwargs())


@mock.patch("deepfellow.suite.utils.install.server_apply")
@mock.patch("deepfellow.suite.utils.install.server_resolve")
@mock.patch("deepfellow.suite.utils.install.server_inspect")
@mock.patch("deepfellow.suite.utils.install.env_get")
def test_server_install_apply_uses_workspace_template_and_infra_api_key(
    mock_env_get: Mock, mock_server_inspect: Mock, mock_server_resolve: Mock, mock_server_apply: Mock
) -> None:
    from deepfellow.suite.utils.install import _server_install_apply

    mock_env_get.return_value = "infra-api-key"

    _server_install_apply("Admin", "admin@example.com", "Sup3r$ecret!", True, **_server_install_apply_kwargs())

    assert mock_server_inspect.call_args.kwargs["template"] == "workspace"
    assert mock_server_inspect.call_args.kwargs["force_install"] is True
    assert mock_server_inspect.call_args.kwargs["admin_email"] == "admin@example.com"
    assert mock_server_resolve.call_args.kwargs["infra_api_key"] == "infra-api-key"
    # infra_api_key is always freshly read from the infra suite just installed, never a CLI flag -
    # it must never be silently outranked by a future template's own "infra_api_key", unlike
    # port/docker_network, whose explicit status genuinely depends on what the user passed.
    assert "infra_api_key" in mock_server_resolve.call_args.kwargs["explicitly_provided"]
    assert mock_server_apply.call_args == mock.call(mock_server_resolve.return_value, will_auto_start=True)


@mock.patch("deepfellow.suite.utils.install.env_get")
def test_server_install_apply_reads_infra_api_key_from_given_infra_directory(mock_env_get: Mock) -> None:
    """A custom infra_directory must be reflected in where the freshly-installed infra's own
    DF_INFRA_API_KEY is read back from - not the fixed DF_INFRA_DIRECTORY default."""
    from deepfellow.suite.utils.install import _server_install_apply

    custom_infra_directory = Path("/custom/infra")
    mock_env_get.return_value = None

    with pytest.raises(InstallError, match="DF_INFRA_API_KEY not found"):
        _server_install_apply(
            "Admin",
            "admin@example.com",
            "Sup3r$ecret!",
            False,
            **_server_install_apply_kwargs(infra_directory=custom_infra_directory),
        )

    assert mock_env_get.call_args == mock.call(custom_infra_directory / ".env", "DF_INFRA_API_KEY")


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


@mock.patch("deepfellow.suite.utils.install.create_admin_util")
def test_server_create_admin_calls_create_admin_util(mock_create_admin_util: Mock) -> None:
    from deepfellow.suite.utils.install import _server_create_admin

    mock_create_admin_util.return_value = True

    _server_create_admin("Admin", "admin@example.com", "Sup3r$ecret!", DF_SERVER_DIRECTORY, False)

    assert mock_create_admin_util.call_count == 1
    assert mock_create_admin_util.call_args.kwargs["name"] == "Admin"
    assert mock_create_admin_util.call_args.kwargs["email"] == "admin@example.com"
    assert mock_create_admin_util.call_args.kwargs["password"] == "Sup3r$ecret!"
    assert mock_create_admin_util.call_args.kwargs["directory"] == DF_SERVER_DIRECTORY


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.create_admin_util")
def test_server_create_admin_warns_when_override_ignored_by_existing_account(
    mock_create_admin_util: Mock, mock_echo: Mock
) -> None:
    """An explicit --admin-* override that turns out to target an already-existing admin is
    silently discarded by create_admin_util (it only ever creates or no-ops) - must be surfaced."""
    from deepfellow.suite.utils.install import _server_create_admin

    mock_create_admin_util.return_value = False  # already existed, no-op

    _server_create_admin("Bobby", "admin@example.com", "Sup3r$ecret!", DF_SERVER_DIRECTORY, True)

    assert mock_echo.warning.call_count == 1
    assert "admin@example.com" in mock_echo.warning.call_args.args[0]


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.create_admin_util")
def test_server_create_admin_no_warning_when_not_overridden(mock_create_admin_util: Mock, mock_echo: Mock) -> None:
    """A prior run's persisted admin (not an explicit override this run) hitting the same
    already-exists no-op is expected, not a mistake - no warning."""
    from deepfellow.suite.utils.install import _server_create_admin

    mock_create_admin_util.return_value = False  # already existed, no-op

    _server_create_admin("Admin", "admin@example.com", "Sup3r$ecret!", DF_SERVER_DIRECTORY, False)

    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.create_admin_util")
def test_server_create_admin_no_warning_when_override_created_fresh(
    mock_create_admin_util: Mock, mock_echo: Mock
) -> None:
    """An override that actually applies (no pre-existing account for that email) is not a
    silently-discarded change - no warning."""
    from deepfellow.suite.utils.install import _server_create_admin

    mock_create_admin_util.return_value = True  # newly created

    _server_create_admin("Bobby", "bobby@example.com", "Sup3r$ecret!", DF_SERVER_DIRECTORY, True)

    assert mock_echo.warning.call_count == 0
