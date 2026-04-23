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

from deepfellow.server.utils.users import UserActionError, create_admin


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


# ── create_admin HTTPException handling ─────────────────────────────────────


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
