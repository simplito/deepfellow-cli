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

from deepfellow.server.organization.delete import delete
from deepfellow.server.organization.utils import Organization


@mock.patch("deepfellow.server.organization.delete.state")
@mock.patch("deepfellow.server.organization.delete.echo.debug")
@mock.patch("deepfellow.server.organization.delete.echo.info")
@mock.patch("deepfellow.server.organization.delete.echo.confirm")
@mock.patch("deepfellow.server.organization.delete.delete_organization")
@mock.patch("deepfellow.server.organization.delete.get_organization")
@mock.patch("deepfellow.server.organization.delete.get_token")
@mock.patch("deepfellow.server.organization.delete.get_server_url")
def test_delete_calls_delete_organization_when_confirmed(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_organization: Mock,
    mock_delete_organization: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
) -> None:
    mock_state.yes = False
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    organization = Organization(id="org-id", created_at=0.0, name="Acme", owner_id="owner-id")
    mock_get_organization.return_value = organization
    mock_confirm.return_value = True

    delete(server=None, organization_id="org-id")

    assert mock_delete_organization.call_count == 1
    assert mock_delete_organization.call_args == mock.call("https://server", "org-id", "token")
    assert mock_info.call_args == mock.call("Deleted Acme")


@mock.patch("deepfellow.server.organization.delete.state")
@mock.patch("deepfellow.server.organization.delete.echo.debug")
@mock.patch("deepfellow.server.organization.delete.echo.info")
@mock.patch("deepfellow.server.organization.delete.echo.confirm")
@mock.patch("deepfellow.server.organization.delete.delete_organization")
@mock.patch("deepfellow.server.organization.delete.get_organization")
@mock.patch("deepfellow.server.organization.delete.get_token")
@mock.patch("deepfellow.server.organization.delete.get_server_url")
def test_delete_raises_exit_when_declined(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_organization: Mock,
    mock_delete_organization: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
) -> None:
    mock_state.yes = False
    organization = Organization(id="org-id", created_at=0.0, name="Acme", owner_id="owner-id")
    mock_get_organization.return_value = organization
    mock_confirm.return_value = False

    with pytest.raises(typer.Exit) as exc_info:
        delete(server=None, organization_id="org-id")

    assert exc_info.value.exit_code == 1
    assert mock_delete_organization.call_count == 0


@mock.patch("deepfellow.server.organization.delete.state")
@mock.patch("deepfellow.server.organization.delete.echo.debug")
@mock.patch("deepfellow.server.organization.delete.echo.info")
@mock.patch("deepfellow.server.organization.delete.echo.confirm")
@mock.patch("deepfellow.server.organization.delete.delete_organization")
@mock.patch("deepfellow.server.organization.delete.get_organization")
@mock.patch("deepfellow.server.organization.delete.get_token")
@mock.patch("deepfellow.server.organization.delete.get_server_url")
def test_delete_skips_confirm_prompt_when_yes(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_organization: Mock,
    mock_delete_organization: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
) -> None:
    mock_state.yes = True
    organization = Organization(id="org-id", created_at=0.0, name="Acme", owner_id="owner-id")
    mock_get_organization.return_value = organization

    delete(server=None, organization_id="org-id")

    assert mock_confirm.call_count == 0
    assert mock_delete_organization.call_count == 1
    assert mock_info.call_args == mock.call("Deleted Acme")


@mock.patch("deepfellow.server.organization.delete.state")
@mock.patch("deepfellow.server.organization.delete.echo.debug")
@mock.patch("deepfellow.server.organization.delete.echo.info")
@mock.patch("deepfellow.server.organization.delete.echo.confirm")
@mock.patch("deepfellow.server.organization.delete.delete_organization")
@mock.patch("deepfellow.server.organization.delete.get_organization")
@mock.patch("deepfellow.server.organization.delete.get_token")
@mock.patch("deepfellow.server.organization.delete.get_server_url")
def test_delete_logs_debug_message_when_yes(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_organization: Mock,
    mock_delete_organization: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
) -> None:
    mock_state.yes = True
    organization = Organization(id="org-id", created_at=0.0, name="Acme", owner_id="owner-id")
    mock_get_organization.return_value = organization

    delete(server=None, organization_id="org-id")

    assert mock_debug.call_count == 1
    assert mock_debug.call_args == mock.call("Automatically confirming the deletion.")
