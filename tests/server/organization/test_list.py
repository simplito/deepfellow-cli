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

from deepfellow.server.organization.list import list
from deepfellow.server.organization.utils import Organization


@mock.patch("deepfellow.server.organization.list.echo.info")
@mock.patch("deepfellow.server.organization.list.list_organizations")
@mock.patch("deepfellow.server.organization.list.get_token")
@mock.patch("deepfellow.server.organization.list.get_server_url")
@mock.patch("deepfellow.server.organization.list.state")
def test_list_prints_organizations_joined_by_double_newline(
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_list_organizations: Mock,
    mock_info: Mock,
) -> None:
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    organizations = [
        Organization(id="org-1", created_at=0.0, name="Acme", owner_id="owner-1"),
        Organization(id="org-2", created_at=0.0, name="Globex", owner_id="owner-2"),
    ]
    mock_list_organizations.return_value = organizations

    list(server=None)

    assert mock_get_token.call_count == 1
    assert mock_get_token.call_args == mock.call("secrets-file", "https://server")
    assert mock_list_organizations.call_count == 1
    assert mock_list_organizations.call_args == mock.call("https://server", "token")
    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(f"{organizations[0]}\n\n{organizations[1]}")


@mock.patch("deepfellow.server.organization.list.echo.info")
@mock.patch("deepfellow.server.organization.list.list_organizations")
@mock.patch("deepfellow.server.organization.list.get_token")
@mock.patch("deepfellow.server.organization.list.get_server_url")
@mock.patch("deepfellow.server.organization.list.state")
def test_list_prints_empty_string_when_no_organizations(
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_list_organizations: Mock,
    mock_info: Mock,
) -> None:
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_list_organizations.return_value = []

    list(server=None)

    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call("")
