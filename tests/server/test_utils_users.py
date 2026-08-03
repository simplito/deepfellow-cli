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

import pytest
import typer

from deepfellow.common.validation import PASSWORD_REQUIREMENTS
from deepfellow.server.utils.users import UserActionError, create_admin, reset_password


@mock.patch("deepfellow.common.echo.Prompt.ask")
@mock.patch("deepfellow.server.utils.users.validate_email")
@mock.patch("deepfellow.server.utils.users.run")
def test_create_admin_prompt_email_validation_called(
    mock_run: mock.Mock, mock_validate_email: mock.Mock, mock_ask: mock.Mock
):
    mock_validate_email.return_value = "some@email.com"
    mock_ask.side_effect = ("name", "provided@email.com", "Password1!")

    create_admin(Path(), None, None, None)

    assert mock_validate_email.call_count == 1
    assert mock_validate_email.call_args == mock.call("provided@email.com")
    assert "some@email.com" in mock_run.call_args_list[0][0][0]


@mock.patch("deepfellow.common.echo.Prompt.ask")
@mock.patch("deepfellow.server.utils.users.validate_email")
@mock.patch("deepfellow.server.utils.users.run")
def test_create_admin_reprompts_until_password_valid(
    mock_run: mock.Mock, mock_validate_email: mock.Mock, mock_ask: mock.Mock
):
    mock_validate_email.return_value = "a@b.com"
    mock_run.return_value = "Admin created"
    # name, email, invalid password, valid password
    mock_ask.side_effect = ("name", "a@b.com", "short", "Password1!")

    create_admin(Path(), None, None, None)

    assert mock_ask.call_count == 4
    assert "Password1!" in mock_run.call_args_list[0][0][0]


@mock.patch("deepfellow.server.utils.users.echo")
@mock.patch("deepfellow.server.utils.users.run")
def test_create_admin_prints_password_requirements_before_prompting(mock_run: mock.Mock, mock_echo: mock.Mock):
    mock_run.return_value = "Admin created"

    create_admin(Path(), "name", "a@b.com", None)

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(PASSWORD_REQUIREMENTS)


@mock.patch("deepfellow.common.echo.is_interactive", return_value=False)
@mock.patch("deepfellow.server.utils.users.run")
def test_create_admin_non_interactive_missing_password_exits(mock_run: mock.Mock, mock_is_interactive: mock.Mock):
    with pytest.raises(typer.Exit):
        create_admin(Path(), "name", "a@b.com", None)

    assert mock_run.call_count == 0


@mock.patch("deepfellow.server.utils.users.echo")
@mock.patch("deepfellow.server.utils.users.run")
def test_create_admin_http_exception_with_message_shows_server_message(mock_run: mock.Mock, mock_echo: mock.Mock):
    mock_run.side_effect = UserActionError("HTTPException: 422: Password must be at least 10 characters.")

    with pytest.raises(typer.Exit):
        create_admin(Path(), "name", "admin@example.com", "short")

    mock_echo.error.assert_called_once_with("Password must be at least 10 characters.")


@mock.patch("deepfellow.server.utils.users.echo")
@mock.patch("deepfellow.server.utils.users.run")
def test_create_admin_http_exception_without_message_shows_generic_error(mock_run: mock.Mock, mock_echo: mock.Mock):
    mock_run.side_effect = UserActionError("HTTPException: 500:")

    with pytest.raises(typer.Exit):
        create_admin(Path(), "name", "admin@example.com", "somepassword")

    mock_echo.error.assert_called_once_with("Unable to create an admin: 500.")


@mock.patch("deepfellow.server.utils.users.echo")
@mock.patch("deepfellow.server.utils.users.run")
def test_create_admin_http_exception_strips_whitespace_from_server_message(mock_run: mock.Mock, mock_echo: mock.Mock):
    mock_run.side_effect = UserActionError("HTTPException: 400:   Value error, too short.  ")

    with pytest.raises(typer.Exit):
        create_admin(Path(), "name", "admin@example.com", "somepassword")

    mock_echo.error.assert_called_once_with("Value error, too short.")


@mock.patch("deepfellow.server.utils.users.echo")
@mock.patch("deepfellow.server.utils.users.run")
def test_create_admin_already_exists_error_shows_specific_message(mock_run: mock.Mock, mock_echo: mock.Mock):
    mock_run.side_effect = UserActionError("User with that email already exists")

    with pytest.raises(typer.Exit):
        create_admin(Path(), "name", "admin@example.com", "somepassword")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to create an admin: user with that email already exists")


@mock.patch("deepfellow.server.utils.users.echo")
@mock.patch("deepfellow.server.utils.users.run")
def test_create_admin_http_exception_malformed_message_shows_generic_error(mock_run: mock.Mock, mock_echo: mock.Mock):
    mock_run.side_effect = UserActionError("HTTPException without status code")

    with pytest.raises(typer.Exit):
        create_admin(Path(), "name", "admin@example.com", "somepassword")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to create an admin.")


@mock.patch("deepfellow.server.utils.users.echo")
@mock.patch("deepfellow.server.utils.users.run")
def test_create_admin_generic_error_shows_generic_message(mock_run: mock.Mock, mock_echo: mock.Mock):
    mock_run.side_effect = UserActionError("Connection refused")

    with pytest.raises(typer.Exit):
        create_admin(Path(), "name", "admin@example.com", "somepassword")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to create an admin.")


@mock.patch("deepfellow.common.echo.Prompt.ask")
@mock.patch("deepfellow.server.utils.users.validate_email")
@mock.patch("deepfellow.server.utils.users.run")
def test_reset_password_prompts_for_email_and_password_when_missing(
    mock_run: mock.Mock, mock_validate_email: mock.Mock, mock_ask: mock.Mock
):
    mock_validate_email.return_value = "some@email.com"
    mock_ask.side_effect = ("provided@email.com", "Password1!")

    reset_password(Path(), None, None)

    assert mock_validate_email.call_count == 1
    assert mock_validate_email.call_args == mock.call("provided@email.com")
    assert "Password1!" in mock_run.call_args_list[0][0][0]


@mock.patch("deepfellow.server.utils.users.echo")
@mock.patch("deepfellow.server.utils.users.run")
def test_reset_password_success_shows_success_message(mock_run: mock.Mock, mock_echo: mock.Mock):
    mock_run.return_value = "Password changed"

    reset_password(Path(), "admin@example.com", "Password1!")

    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == mock.call("Password changed.")


@mock.patch("deepfellow.server.utils.users.run")
def test_reset_password_calls_set_password_script_with_email_and_password(mock_run: mock.Mock):
    mock_run.return_value = "Password changed"

    reset_password(Path(), "admin@example.com", "Password1!")

    call_command = mock_run.call_args[0][0]
    assert "admin@example.com" in call_command
    assert "Password1!" in call_command
    assert "server.scripts.set_password" in call_command


@mock.patch("deepfellow.server.utils.users.echo")
@mock.patch("deepfellow.server.utils.users.run")
def test_reset_password_user_not_found_shows_specific_message(mock_run: mock.Mock, mock_echo: mock.Mock):
    mock_run.side_effect = UserActionError("User not found")

    with pytest.raises(typer.Exit):
        reset_password(Path(), "admin@example.com", "Password1!")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to set password: User not found.")


@mock.patch("deepfellow.server.utils.users.echo")
@mock.patch("deepfellow.server.utils.users.run")
def test_reset_password_generic_error_shows_generic_message(mock_run: mock.Mock, mock_echo: mock.Mock):
    mock_run.side_effect = UserActionError("Connection refused")

    with pytest.raises(typer.Exit):
        reset_password(Path(), "admin@example.com", "Password1!")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to set password.")
