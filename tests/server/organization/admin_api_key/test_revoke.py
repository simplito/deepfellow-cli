# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.server.organization.admin_api_key.revoke import revoke
from deepfellow.server.organization.admin_api_key.utils import ApiKey


@mock.patch("deepfellow.server.organization.admin_api_key.revoke.state")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.debug")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.info")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.confirm")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.delete_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_token")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_server_url")
def test_revoke_calls_delete_admin_api_key_when_confirmed(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_admin_api_key: Mock,
    mock_delete_admin_api_key: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    api_key: ApiKey,
) -> None:
    mock_state.yes = False
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_admin_api_key.return_value = api_key
    mock_confirm.return_value = True

    revoke(server=None, organization_id="org-id", api_key_id="key-id")

    assert mock_delete_admin_api_key.call_count == 1
    assert mock_delete_admin_api_key.call_args == mock.call("https://server", "token", "org-id", "key-id")
    assert mock_info.call_args == mock.call("API Key revoked.")


@mock.patch("deepfellow.server.organization.admin_api_key.revoke.state")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.debug")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.info")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.confirm")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.delete_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_token")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_server_url")
def test_revoke_prompts_with_api_key_name(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_admin_api_key: Mock,
    mock_delete_admin_api_key: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    api_key: ApiKey,
) -> None:
    mock_state.yes = False
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_admin_api_key.return_value = api_key
    mock_confirm.return_value = True

    revoke(server=None, organization_id="org-id", api_key_id="key-id")

    assert mock_confirm.call_count == 1
    assert mock_confirm.call_args == mock.call(
        "Are you sure you want to delete the Organization API Key my-key?", default=True
    )


@mock.patch("deepfellow.server.organization.admin_api_key.revoke.state")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.debug")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.info")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.confirm")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.delete_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_token")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_server_url")
def test_revoke_raises_exit_when_declined(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_admin_api_key: Mock,
    mock_delete_admin_api_key: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    api_key: ApiKey,
) -> None:
    mock_state.yes = False
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_admin_api_key.return_value = api_key
    mock_confirm.return_value = False

    with pytest.raises(typer.Exit) as exc_info:
        revoke(server=None, organization_id="org-id", api_key_id="key-id")

    assert exc_info.value.exit_code == 1
    assert mock_delete_admin_api_key.call_count == 0


@mock.patch("deepfellow.server.organization.admin_api_key.revoke.state")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.debug")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.info")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.confirm")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.delete_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_token")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_server_url")
def test_revoke_skips_confirm_prompt_when_yes(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_admin_api_key: Mock,
    mock_delete_admin_api_key: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    api_key: ApiKey,
) -> None:
    mock_state.yes = True
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_admin_api_key.return_value = api_key

    revoke(server=None, organization_id="org-id", api_key_id="key-id")

    assert mock_confirm.call_count == 0
    assert mock_delete_admin_api_key.call_count == 1
    assert mock_info.call_args == mock.call("API Key revoked.")


@mock.patch("deepfellow.server.organization.admin_api_key.revoke.state")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.debug")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.info")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.confirm")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.delete_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_token")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_server_url")
def test_revoke_logs_debug_message_when_yes(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_admin_api_key: Mock,
    mock_delete_admin_api_key: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    api_key: ApiKey,
) -> None:
    mock_state.yes = True
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_admin_api_key.return_value = api_key

    revoke(server=None, organization_id="org-id", api_key_id="key-id")

    assert mock_debug.call_count == 1
    assert mock_debug.call_args == mock.call("Automatically confirming the revoke.")


@mock.patch("deepfellow.server.organization.admin_api_key.revoke.state")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.debug")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.info")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.echo.confirm")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.delete_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_token")
@mock.patch("deepfellow.server.organization.admin_api_key.revoke.get_server_url")
def test_revoke_resolves_server_and_token(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_admin_api_key: Mock,
    mock_delete_admin_api_key: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    api_key: ApiKey,
) -> None:
    mock_state.yes = True
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_admin_api_key.return_value = api_key

    revoke(server=None, organization_id="org-id", api_key_id="key-id")

    assert mock_get_server_url.call_count == 1
    assert mock_get_server_url.call_args == mock.call(None)
    assert mock_get_token.call_count == 1
    assert mock_get_token.call_args == mock.call(mock_state.cli_secrets_file, "https://server")
    assert mock_get_admin_api_key.call_count == 1
    assert mock_get_admin_api_key.call_args == mock.call("https://server", "token", "org-id", "key-id")
