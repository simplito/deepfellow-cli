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

from deepfellow.server.project.api_key.revoke import revoke
from deepfellow.server.project.api_key.utils import ApiKey


@mock.patch("deepfellow.server.project.api_key.revoke.state")
@mock.patch("deepfellow.server.project.api_key.revoke.echo.debug")
@mock.patch("deepfellow.server.project.api_key.revoke.echo.info")
@mock.patch("deepfellow.server.project.api_key.revoke.echo.confirm")
@mock.patch("deepfellow.server.project.api_key.revoke.delete_api_key")
@mock.patch("deepfellow.server.project.api_key.revoke.get_api_key")
@mock.patch("deepfellow.server.project.api_key.revoke.get_token")
@mock.patch("deepfellow.server.project.api_key.revoke.get_server_url")
def test_revoke_calls_delete_api_key_when_confirmed(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_api_key: Mock,
    mock_delete_api_key: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
) -> None:
    mock_state.yes = False
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    api_key = ApiKey(
        id="key-id",
        object="organization.project.api_key",
        name="Prod Key",
        redacted_value="sk-***",
        created_at=0.0,
        last_used_at=0.0,
        value=None,
    )
    mock_get_api_key.return_value = api_key
    mock_confirm.return_value = True

    revoke(server=None, organization_id="org-id", project_id="proj-id", api_key_id="key-id")

    assert mock_delete_api_key.call_count == 1
    assert mock_delete_api_key.call_args == mock.call("https://server", "token", "org-id", "proj-id", "key-id")
    assert mock_info.call_args == mock.call("API Key revoked.")


@mock.patch("deepfellow.server.project.api_key.revoke.state")
@mock.patch("deepfellow.server.project.api_key.revoke.echo.debug")
@mock.patch("deepfellow.server.project.api_key.revoke.echo.info")
@mock.patch("deepfellow.server.project.api_key.revoke.echo.confirm")
@mock.patch("deepfellow.server.project.api_key.revoke.delete_api_key")
@mock.patch("deepfellow.server.project.api_key.revoke.get_api_key")
@mock.patch("deepfellow.server.project.api_key.revoke.get_token")
@mock.patch("deepfellow.server.project.api_key.revoke.get_server_url")
def test_revoke_raises_exit_when_declined(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_api_key: Mock,
    mock_delete_api_key: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
) -> None:
    mock_state.yes = False
    api_key = ApiKey(
        id="key-id",
        object="organization.project.api_key",
        name="Prod Key",
        redacted_value="sk-***",
        created_at=0.0,
        last_used_at=0.0,
        value=None,
    )
    mock_get_api_key.return_value = api_key
    mock_confirm.return_value = False

    with pytest.raises(typer.Exit) as exc_info:
        revoke(server=None, organization_id="org-id", project_id="proj-id", api_key_id="key-id")

    assert exc_info.value.exit_code == 1
    assert mock_delete_api_key.call_count == 0


@mock.patch("deepfellow.server.project.api_key.revoke.state")
@mock.patch("deepfellow.server.project.api_key.revoke.echo.debug")
@mock.patch("deepfellow.server.project.api_key.revoke.echo.info")
@mock.patch("deepfellow.server.project.api_key.revoke.echo.confirm")
@mock.patch("deepfellow.server.project.api_key.revoke.delete_api_key")
@mock.patch("deepfellow.server.project.api_key.revoke.get_api_key")
@mock.patch("deepfellow.server.project.api_key.revoke.get_token")
@mock.patch("deepfellow.server.project.api_key.revoke.get_server_url")
def test_revoke_skips_confirm_prompt_when_yes(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_api_key: Mock,
    mock_delete_api_key: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
) -> None:
    mock_state.yes = True
    api_key = ApiKey(
        id="key-id",
        object="organization.project.api_key",
        name="Prod Key",
        redacted_value="sk-***",
        created_at=0.0,
        last_used_at=0.0,
        value=None,
    )
    mock_get_api_key.return_value = api_key

    revoke(server=None, organization_id="org-id", project_id="proj-id", api_key_id="key-id")

    assert mock_confirm.call_count == 0
    assert mock_delete_api_key.call_count == 1
    assert mock_info.call_args == mock.call("API Key revoked.")


@mock.patch("deepfellow.server.project.api_key.revoke.state")
@mock.patch("deepfellow.server.project.api_key.revoke.echo.debug")
@mock.patch("deepfellow.server.project.api_key.revoke.echo.info")
@mock.patch("deepfellow.server.project.api_key.revoke.echo.confirm")
@mock.patch("deepfellow.server.project.api_key.revoke.delete_api_key")
@mock.patch("deepfellow.server.project.api_key.revoke.get_api_key")
@mock.patch("deepfellow.server.project.api_key.revoke.get_token")
@mock.patch("deepfellow.server.project.api_key.revoke.get_server_url")
def test_revoke_logs_debug_message_when_yes(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_api_key: Mock,
    mock_delete_api_key: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
) -> None:
    mock_state.yes = True
    api_key = ApiKey(
        id="key-id",
        object="organization.project.api_key",
        name="Prod Key",
        redacted_value="sk-***",
        created_at=0.0,
        last_used_at=0.0,
        value=None,
    )
    mock_get_api_key.return_value = api_key

    revoke(server=None, organization_id="org-id", project_id="proj-id", api_key_id="key-id")

    assert mock_debug.call_count == 1
    assert mock_debug.call_args == mock.call("Automatically confirming the revoke.")
