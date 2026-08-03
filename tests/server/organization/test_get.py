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

from deepfellow.server.organization.get import get
from deepfellow.server.organization.utils import Organization


@mock.patch("deepfellow.server.organization.get.echo.info")
@mock.patch("deepfellow.server.organization.get.get_organization")
@mock.patch("deepfellow.server.organization.get.get_token")
@mock.patch("deepfellow.server.organization.get.get_server_url")
def test_get_prints_organization_info(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_organization: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    organization = Organization(id="org-id", created_at=0.0, name="Acme", owner_id="owner-id")
    mock_get_organization.return_value = organization

    get(server=None, organization_id="org-id")

    assert mock_get_organization.call_count == 1
    assert mock_get_organization.call_args == mock.call("https://server", "org-id", "token")
    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(str(organization))


@mock.patch("deepfellow.server.organization.get.echo.info")
@mock.patch("deepfellow.server.organization.get.get_organization")
@mock.patch("deepfellow.server.organization.get.get_token")
@mock.patch("deepfellow.server.organization.get.get_server_url")
def test_get_resolves_token_using_server_url(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_organization: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    organization = Organization(id="org-id", created_at=0.0, name="Acme", owner_id="owner-id")
    mock_get_organization.return_value = organization

    get(server="https://server", organization_id="org-id")

    assert mock_get_server_url.call_count == 1
    assert mock_get_server_url.call_args == mock.call("https://server")
    assert mock_get_token.call_count == 1
    assert mock_get_token.call_args == mock.call(mock.ANY, "https://server")
