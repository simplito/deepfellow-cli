# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Tests for the server create_admin command."""

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.server.create_admin import create_admin


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    return tmp_path


@mock.patch("deepfellow.server.create_admin.get_token_from_login")
@mock.patch("deepfellow.server.create_admin.rest")
@mock.patch("deepfellow.server.create_admin.echo")
@mock.patch("deepfellow.server.create_admin.apply_admin", return_value=True)
@mock.patch("deepfellow.server.create_admin.resolve_admin_creds")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_creates_admin_with_resolved_credentials(
    mock_check_server_directory: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    mock_echo: Mock,
    mock_rest: Mock,
    mock_get_token_from_login: Mock,
    directory: Path,
):
    mock_resolve_admin_creds.return_value = ("Ada", "ada@b.com", "hunter2hunter")
    mock_echo.confirm.return_value = False

    create_admin(directory=directory, name=None, email="ada@b.com", password=None)

    assert mock_check_server_directory.call_args == mock.call(directory)
    assert mock_resolve_admin_creds.call_args == mock.call(None, "ada@b.com", None)
    assert mock_apply_admin.call_args == mock.call(
        directory, "Ada", "ada@b.com", "hunter2hunter", silent_if_exists=True
    )
    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.server.create_admin.get_token_from_login")
@mock.patch("deepfellow.server.create_admin.rest")
@mock.patch("deepfellow.server.create_admin.echo")
@mock.patch("deepfellow.server.create_admin.apply_admin", return_value=True)
@mock.patch("deepfellow.server.create_admin.resolve_admin_creds")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_checks_directory_before_prompting_for_credentials_and_creating_admin(
    mock_check_server_directory: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    mock_echo: Mock,
    mock_rest: Mock,
    mock_get_token_from_login: Mock,
    directory: Path,
):
    mock_resolve_admin_creds.return_value = ("Ada", "ada@b.com", "hunter2hunter")
    mock_echo.confirm.return_value = False
    manager = Mock()
    manager.attach_mock(mock_check_server_directory, "check_server_directory")
    manager.attach_mock(mock_resolve_admin_creds, "resolve_admin_creds")
    manager.attach_mock(mock_apply_admin, "apply_admin")

    create_admin(directory=directory, name=None, email=None, password=None)

    assert [call[0] for call in manager.mock_calls] == ["check_server_directory", "resolve_admin_creds", "apply_admin"]


@mock.patch("deepfellow.server.create_admin.state")
@mock.patch("deepfellow.server.create_admin.get_token_from_login")
@mock.patch("deepfellow.server.create_admin.rest")
@mock.patch("deepfellow.server.create_admin.echo")
@mock.patch("deepfellow.server.create_admin.apply_admin", return_value=True)
@mock.patch("deepfellow.server.create_admin.resolve_admin_creds")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_logs_in_when_user_confirms(
    mock_check_server_directory: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    mock_echo: Mock,
    mock_rest: Mock,
    mock_get_token_from_login: Mock,
    mock_state: Mock,
    directory: Path,
):
    mock_resolve_admin_creds.return_value = ("Ada", "ada@b.com", "hunter2hunter")
    mock_state.non_interactive = False
    mock_echo.confirm.return_value = True
    mock_rest.get_server_url.return_value = "http://server"

    create_admin(directory=directory, name="Ada", email="ada@b.com", password="hunter2hunter")

    assert mock_echo.confirm.call_args == mock.call("Do you want to log in as the new admin now?", default=True)
    assert mock_rest.get_server_url.call_args == mock.call(None)
    assert mock_get_token_from_login.call_args == mock.call(
        mock_state.cli_secrets_file, "http://server", email="ada@b.com", password="hunter2hunter"
    )


@mock.patch("deepfellow.server.create_admin.get_token_from_login")
@mock.patch("deepfellow.server.create_admin.rest")
@mock.patch("deepfellow.server.create_admin.echo")
@mock.patch("deepfellow.server.create_admin.apply_admin", return_value=True)
@mock.patch("deepfellow.server.create_admin.resolve_admin_creds")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_does_not_log_in_when_user_declines(
    mock_check_server_directory: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    mock_echo: Mock,
    mock_rest: Mock,
    mock_get_token_from_login: Mock,
    directory: Path,
):
    mock_resolve_admin_creds.return_value = ("Ada", "ada@b.com", "hunter2hunter")
    mock_echo.confirm.return_value = False

    create_admin(directory=directory, name="Ada", email="ada@b.com", password="hunter2hunter")

    assert mock_get_token_from_login.call_count == 0
    assert mock_rest.get_server_url.call_count == 0


@mock.patch("deepfellow.server.create_admin.get_token_from_login")
@mock.patch("deepfellow.server.create_admin.echo")
@mock.patch("deepfellow.server.create_admin.apply_admin", return_value=False)
@mock.patch("deepfellow.server.create_admin.resolve_admin_creds")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_exits_with_error_when_admin_already_exists(
    mock_check_server_directory: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    mock_echo: Mock,
    mock_get_token_from_login: Mock,
    directory: Path,
):
    """Unlike suite install's/a --template reinstall's own create-admin step, this direct command
    has no resume context - an existing admin means IT failed to do what was asked, not a no-op."""
    mock_resolve_admin_creds.return_value = ("Ada", "ada@b.com", "hunter2hunter")

    with pytest.raises(typer.Exit):
        create_admin(directory=directory, name="Ada", email="ada@b.com", password="hunter2hunter")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "Unable to create an admin: an account with that email already exists."
    )
    assert mock_echo.confirm.call_count == 0
    assert mock_get_token_from_login.call_count == 0


@mock.patch("deepfellow.server.create_admin.state")
@mock.patch("deepfellow.server.create_admin.get_token_from_login", side_effect=typer.Exit(1))
@mock.patch("deepfellow.server.create_admin.rest")
@mock.patch("deepfellow.server.create_admin.echo")
@mock.patch("deepfellow.server.create_admin.apply_admin", return_value=True)
@mock.patch("deepfellow.server.create_admin.resolve_admin_creds")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_warns_instead_of_failing_when_login_fails(
    mock_check_server_directory: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    mock_echo: Mock,
    mock_rest: Mock,
    mock_get_token_from_login: Mock,
    mock_state: Mock,
    directory: Path,
):
    mock_resolve_admin_creds.return_value = ("Ada", "ada@b.com", "hunter2hunter")
    mock_echo.confirm.return_value = True

    create_admin(directory=directory, name="Ada", email="ada@b.com", password="hunter2hunter")

    assert mock_echo.warning.call_count == 1
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.server.create_admin.state")
@mock.patch("deepfellow.server.create_admin.get_token_from_login")
@mock.patch("deepfellow.server.create_admin.rest")
@mock.patch("deepfellow.server.create_admin.echo")
@mock.patch("deepfellow.server.create_admin.apply_admin", return_value=True)
@mock.patch("deepfellow.server.create_admin.resolve_admin_creds")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_defaults_to_no_login_in_non_interactive_mode(
    mock_check_server_directory: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    mock_echo: Mock,
    mock_rest: Mock,
    mock_get_token_from_login: Mock,
    mock_state: Mock,
    directory: Path,
):
    mock_resolve_admin_creds.return_value = ("Ada", "ada@b.com", "hunter2hunter")
    mock_state.non_interactive = True
    mock_echo.confirm.return_value = False

    create_admin(directory=directory, name="Ada", email="ada@b.com", password="hunter2hunter")

    assert mock_echo.confirm.call_args == mock.call("Do you want to log in as the new admin now?", default=False)


@mock.patch("deepfellow.server.create_admin.state")
@mock.patch("deepfellow.server.create_admin.get_token_from_login", side_effect=typer.Exit(0))
@mock.patch("deepfellow.server.create_admin.rest")
@mock.patch("deepfellow.server.create_admin.echo")
@mock.patch("deepfellow.server.create_admin.apply_admin", return_value=True)
@mock.patch("deepfellow.server.create_admin.resolve_admin_creds")
@mock.patch("deepfellow.server.create_admin.check_server_directory")
def test_create_admin_does_not_report_failed_login_on_clean_exit(
    mock_check_server_directory: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    mock_echo: Mock,
    mock_rest: Mock,
    mock_get_token_from_login: Mock,
    mock_state: Mock,
    directory: Path,
) -> None:
    mock_resolve_admin_creds.return_value = ("Ada", "ada@b.com", "hunter2hunter")
    mock_echo.confirm.return_value = True

    with pytest.raises(typer.Exit):
        create_admin(directory=directory, name="Ada", email="ada@b.com", password="hunter2hunter")

    assert mock_echo.warning.call_count == 0
