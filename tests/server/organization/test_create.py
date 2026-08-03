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

from deepfellow.server.organization.create import create
from deepfellow.server.organization.utils import Organization


@mock.patch("deepfellow.server.organization.create.echo.info")
@mock.patch("deepfellow.server.organization.create.create_organization")
@mock.patch("deepfellow.server.organization.create.get_token")
@mock.patch("deepfellow.server.organization.create.get_server_url")
def test_create_calls_create_organization_with_server_and_name(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_create_organization: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    organization = Organization(id="org-id", created_at=0.0, name="Acme", owner_id="owner-id")
    mock_create_organization.return_value = organization

    create(server=None, name="Acme")

    assert mock_create_organization.call_count == 1
    assert mock_create_organization.call_args == mock.call("https://server", "token", "Acme")


@mock.patch("deepfellow.server.organization.create.echo.info")
@mock.patch("deepfellow.server.organization.create.create_organization")
@mock.patch("deepfellow.server.organization.create.get_token")
@mock.patch("deepfellow.server.organization.create.get_server_url")
def test_create_prints_created_organization(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_create_organization: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    organization = Organization(id="org-id", created_at=0.0, name="Acme", owner_id="owner-id")
    mock_create_organization.return_value = organization

    create(server=None, name="Acme")

    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(str(organization))


@mock.patch("deepfellow.server.organization.create.echo.info")
@mock.patch("deepfellow.server.organization.create.create_organization")
@mock.patch("deepfellow.server.organization.create.get_token")
@mock.patch("deepfellow.server.organization.create.get_server_url")
def test_create_resolves_token_from_server_url(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_create_organization: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    organization = Organization(id="org-id", created_at=0.0, name="Acme", owner_id="owner-id")
    mock_create_organization.return_value = organization

    create(server="https://server", name="Acme")

    assert mock_get_server_url.call_count == 1
    assert mock_get_server_url.call_args == mock.call("https://server")
    assert mock_get_token.call_count == 1
    assert mock_get_token.call_args[0][1] == "https://server"
