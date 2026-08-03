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

from deepfellow.common.state import state
from deepfellow.server.organization.admin_api_key.create import create
from deepfellow.server.organization.admin_api_key.utils import ApiKey


@mock.patch("deepfellow.server.organization.admin_api_key.create.echo.info")
@mock.patch("deepfellow.server.organization.admin_api_key.create.create_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.create.get_token")
@mock.patch("deepfellow.server.organization.admin_api_key.create.get_server_url")
def test_create_calls_create_admin_api_key_with_resolved_server_and_token(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_create_admin_api_key: Mock,
    mock_info: Mock,
    api_key: ApiKey,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_create_admin_api_key.return_value = api_key

    create(server=None, organization_id="org-id", name="my-key")

    assert mock_get_server_url.call_count == 1
    assert mock_get_server_url.call_args == mock.call(None)
    assert mock_get_token.call_count == 1
    assert mock_get_token.call_args == mock.call(state.cli_secrets_file, "https://server")
    assert mock_create_admin_api_key.call_count == 1
    assert mock_create_admin_api_key.call_args == mock.call("https://server", "token", "org-id", "my-key")


@mock.patch("deepfellow.server.organization.admin_api_key.create.echo.info")
@mock.patch("deepfellow.server.organization.admin_api_key.create.create_admin_api_key")
@mock.patch("deepfellow.server.organization.admin_api_key.create.get_token")
@mock.patch("deepfellow.server.organization.admin_api_key.create.get_server_url")
def test_create_echoes_created_api_key(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_create_admin_api_key: Mock,
    mock_info: Mock,
    api_key: ApiKey,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_create_admin_api_key.return_value = api_key

    create(server=None, organization_id="org-id", name="my-key")

    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(str(api_key))
