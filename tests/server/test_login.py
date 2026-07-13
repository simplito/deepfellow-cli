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

from deepfellow.server.login import login

SERVER = "http://localhost:8000"


@mock.patch("deepfellow.server.login.echo")
@mock.patch("deepfellow.server.login.register_token")
@mock.patch("deepfellow.server.login.get_token_from_login")
@mock.patch("deepfellow.server.login.get_server_url", return_value=SERVER)
def test_login_with_token_registers_token_instead_of_password_login(
    mock_server_url: Mock,
    mock_login: Mock,
    mock_register: Mock,
    mock_echo: Mock,
) -> None:
    login(server=None, email=None, password=None, token="dfuser_abc")

    assert mock_register.call_count == 1
    assert mock_register.call_args == mock.call(mock.ANY, SERVER, "dfuser_abc")
    assert mock_login.call_count == 0


@mock.patch("deepfellow.server.login.echo")
@mock.patch("deepfellow.server.login.register_token")
@mock.patch("deepfellow.server.login.get_token_from_login")
@mock.patch("deepfellow.server.login.get_server_url", return_value=SERVER)
def test_login_without_token_uses_password_login(
    mock_server_url: Mock,
    mock_login: Mock,
    mock_register: Mock,
    mock_echo: Mock,
) -> None:
    login(server=None, email="user@example.com", password="password123", token=None)

    assert mock_login.call_count == 1
    assert mock_login.call_args == mock.call(mock.ANY, SERVER, email="user@example.com", password="password123")
    assert mock_register.call_count == 0
