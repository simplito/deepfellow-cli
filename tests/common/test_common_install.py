# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.exceptions import InstallError
from deepfellow.common.install import (
    assert_docker,
    ensure_directory,
    resolve_admin_kwargs,
    validate_non_interactive_admin_values,
)
from deepfellow.common.state import state


@mock.patch("deepfellow.common.install.echo")
@mock.patch("deepfellow.common.install.is_docker_installed")
@mock.patch("deepfellow.common.install.is_docker_compose_installed")
@mock.patch("deepfellow.common.install.is_user_allowed_to_use_docker")
def test_assert_docker_installed(
    mock_is_user_allowed_to_use_docker: Mock,
    mock_is_docker_compose_installed: Mock,
    mock_is_docker_installed: Mock,
    mock_echo: Mock,
) -> None:
    assert_docker()

    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.common.install.echo")
@mock.patch("deepfellow.common.install.is_docker_installed")
def test_assert_docker_not_installed(mock_is_docker_installed: Mock, mock_echo: Mock) -> None:
    mock_is_docker_installed.return_value = False

    with pytest.raises(typer.Exit):
        assert_docker()

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Missing docker. Install docker.")


@mock.patch("deepfellow.common.install.echo")
@mock.patch("deepfellow.common.install.is_docker_installed")
@mock.patch("deepfellow.common.install.is_docker_compose_installed")
def test_assert_docker_compose_not_installed(
    mock_is_docker_compose_installed: Mock, mock_is_docker_installed: Mock, mock_echo: Mock
) -> None:
    mock_is_docker_compose_installed.return_value = False

    with pytest.raises(typer.Exit):
        assert_docker()

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Missing docker compose plugin. Install docker compose.")


@mock.patch("deepfellow.common.install.echo")
@mock.patch("deepfellow.common.install.is_docker_installed")
@mock.patch("deepfellow.common.install.is_docker_compose_installed")
@mock.patch("deepfellow.common.install.is_user_allowed_to_use_docker")
@mock.patch("deepfellow.common.install.is_user_in_docker_group")
@mock.patch("deepfellow.common.install.is_docker_group_available")
def test_assert_docker_unable_to_run(
    mock_is_docker_group_available: Mock,
    mock_is_user_in_docker_group: Mock,
    mock_is_user_allowed_to_use_docker: Mock,
    mock_is_docker_compose_installed: Mock,
    mock_is_docker_installed: Mock,
    mock_echo: Mock,
) -> None:
    mock_is_user_allowed_to_use_docker.return_value = False

    with pytest.raises(typer.Exit):
        assert_docker()

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to run docker command.")


@mock.patch("deepfellow.common.install.echo")
@mock.patch("deepfellow.common.install.is_docker_installed")
@mock.patch("deepfellow.common.install.is_docker_compose_installed")
@mock.patch("deepfellow.common.install.is_user_allowed_to_use_docker")
@mock.patch("deepfellow.common.install.is_user_in_docker_group")
@mock.patch("deepfellow.common.install.is_docker_group_available")
@mock.patch("deepfellow.common.install.getpass.getuser")
def test_assert_docker_prompts_usermod_when_group_available(
    mock_getuser: Mock,
    mock_is_docker_group_available: Mock,
    mock_is_user_in_docker_group: Mock,
    mock_is_user_allowed_to_use_docker: Mock,
    mock_is_docker_compose_installed: Mock,
    mock_is_docker_installed: Mock,
    mock_echo: Mock,
) -> None:
    mock_is_user_allowed_to_use_docker.return_value = False
    mock_is_user_in_docker_group.return_value = False
    mock_is_docker_group_available.return_value = True
    mock_getuser.return_value = "alice"

    with pytest.raises(typer.Exit):
        assert_docker()

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call("Add user to the docker group. `usermod -aG docker alice`")


@mock.patch("deepfellow.common.install.echo")
def test_ensure_directory_creates_directory_when_missing(mock_echo: Mock, tmp_path: Path) -> None:
    directory = tmp_path / "new_dir"

    ensure_directory(directory)

    assert directory.is_dir() is True
    assert mock_echo.warning.call_count == 0
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.common.install.echo")
def test_ensure_directory_raises_when_existing_and_user_declines(mock_echo: Mock, tmp_path: Path) -> None:
    mock_echo.confirm.return_value = False

    with pytest.raises(typer.Exit):
        ensure_directory(tmp_path)

    assert mock_echo.warning.call_count == 1
    assert mock_echo.warning.call_args == mock.call(f"Directory {tmp_path} already exists.")
    assert mock_echo.confirm.call_count == 1
    assert mock_echo.confirm.call_args == mock.call("Should I override existing installation?")


@mock.patch("deepfellow.common.install.echo")
def test_ensure_directory_overrides_when_existing_and_user_confirms(mock_echo: Mock, tmp_path: Path) -> None:
    mock_echo.confirm.return_value = True

    ensure_directory(tmp_path)

    assert mock_echo.confirm.call_count == 1
    assert tmp_path.is_dir() is True


@mock.patch("deepfellow.common.install.echo")
@mock.patch("deepfellow.common.install.is_interactive")
def test_ensure_directory_shows_guidance_when_non_interactive_and_existing(
    mock_is_interactive: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    mock_is_interactive.return_value = False
    mock_echo.confirm.return_value = False

    with pytest.raises(typer.Exit):
        ensure_directory(tmp_path)

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(
        "Non-interactive mode is ON. To force a reinstall over the existing installation, pass "
        f"--force-install, or remove the directory manually: rm -rf {tmp_path}"
    )


@mock.patch("deepfellow.common.install.echo")
def test_ensure_directory_skips_confirmation_when_force_install(mock_echo: Mock, tmp_path: Path) -> None:
    ensure_directory(tmp_path, force_install=True)

    assert mock_echo.warning.call_count == 0
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.common.install.echo")
def test_ensure_directory_overwrite_true_skips_prompt_and_proceeds(mock_echo: Mock, tmp_path: Path) -> None:
    ensure_directory(tmp_path, overwrite=True)

    assert mock_echo.warning.call_count == 0
    assert mock_echo.confirm.call_count == 0
    assert tmp_path.is_dir() is True


@mock.patch("deepfellow.common.install.echo")
def test_ensure_directory_overwrite_false_aborts_without_prompt(mock_echo: Mock, tmp_path: Path) -> None:
    with pytest.raises(typer.Exit):
        ensure_directory(tmp_path, overwrite=False)

    assert mock_echo.warning.call_count == 0
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.common.install.echo")
def test_ensure_directory_overwrite_false_ignored_when_directory_missing(mock_echo: Mock, tmp_path: Path) -> None:
    directory = tmp_path / "new_dir"

    ensure_directory(directory, overwrite=False)

    assert directory.is_dir() is True
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.common.install.reraise_if_debug")
@mock.patch("pathlib.Path.mkdir")
@mock.patch("deepfellow.common.install.echo")
def test_ensure_directory_calls_reraise_if_debug_on_mkdir_failure(
    mock_echo: Mock,
    mock_mkdir: Mock,
    mock_reraise_if_debug: Mock,
    tmp_path: Path,
) -> None:
    directory = tmp_path / "blocked"
    mock_mkdir.side_effect = OSError("boom")

    ensure_directory(directory)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(f"Unable to create directory {directory}.")
    assert mock_reraise_if_debug.call_count == 1
    assert mock_reraise_if_debug.call_args == mock.call(mock_mkdir.side_effect)


def test_resolve_admin_kwargs_cli_value_wins_over_action_kwargs() -> None:
    action_kwargs = {"name": "Action Name", "email": "action@example.com", "password": "action-pass"}

    effective = resolve_admin_kwargs(action_kwargs, "CLI Name", "cli@example.com", "cli-pass")

    assert effective == {"name": "CLI Name", "email": "cli@example.com", "password": "cli-pass"}


@pytest.mark.parametrize(("admin_name", "admin_email", "admin_password"), [(None, "", None), ("", None, "")])
def test_resolve_admin_kwargs_falls_back_to_action_kwargs_when_cli_value_falsy(
    admin_name: str | None, admin_email: str | None, admin_password: str | None
) -> None:
    action_kwargs = {"name": "Action Name", "email": "action@example.com", "password": "action-pass"}

    effective = resolve_admin_kwargs(action_kwargs, admin_name, admin_email, admin_password)

    assert effective == {"name": "Action Name", "email": "action@example.com", "password": "action-pass"}


def test_resolve_admin_kwargs_both_missing_yields_none() -> None:
    effective = resolve_admin_kwargs({}, None, None, None)

    assert effective == {"name": None, "email": None, "password": None}


def test_validate_non_interactive_admin_values_is_noop_when_not_non_interactive() -> None:
    state.non_interactive = False

    validate_non_interactive_admin_values({"name": None, "email": None, "password": None}, "suite install")


def test_validate_non_interactive_admin_values_raises_naming_missing_keys() -> None:
    state.non_interactive = True

    with pytest.raises(InstallError) as exc_info:
        validate_non_interactive_admin_values(
            {"name": None, "email": "admin@example.com", "password": None}, "suite install"
        )

    assert str(exc_info.value) == (
        "suite install is missing name, password; --non-interactive has no prompt to fall back on. "
        "Pass --admin-name/--admin-email/--admin-password"
    )


def test_validate_non_interactive_admin_values_raises_naming_single_missing_key() -> None:
    state.non_interactive = True

    with pytest.raises(InstallError) as exc_info:
        validate_non_interactive_admin_values(
            {"name": "Admin", "email": "admin@example.com", "password": None}, "suite install"
        )

    assert str(exc_info.value) == (
        "suite install is missing password; --non-interactive has no prompt to fall back on. "
        "Pass --admin-name/--admin-email/--admin-password"
    )


def test_validate_non_interactive_admin_values_is_noop_when_nothing_missing() -> None:
    state.non_interactive = True

    validate_non_interactive_admin_values(
        {"name": "Admin", "email": "admin@example.com", "password": "pass"}, "suite install"
    )
