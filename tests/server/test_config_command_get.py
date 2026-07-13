# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from unittest import mock
from unittest.mock import Mock

from deepfellow.server.config_command.get import get_

SERVER = "http://localhost:8000"


@mock.patch("deepfellow.server.config_command.get.echo")
@mock.patch("deepfellow.server.config_command.get.http_get")
@mock.patch("deepfellow.server.config_command.get.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.config_command.get.get_server_url", return_value=SERVER)
def test_get_prints_config_from_admin_endpoint(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_http_get.return_value = {"otel_tracing_enabled": True}

    get_(server=None)

    assert mock_http_get.call_count == 1
    assert mock_http_get.call_args == mock.call(f"{SERVER}/admin/config", "dfuser_abc", item_name="Server config")
    assert mock_echo.info.call_count == 1


@mock.patch("deepfellow.server.config_command.get.echo")
@mock.patch("deepfellow.server.config_command.get.http_get")
@mock.patch("deepfellow.server.config_command.get.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.config_command.get.get_server_url", return_value=SERVER)
def test_get_without_secret_flag_does_not_reveal(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_http_get.return_value = {"smtp": {"password": "••••••••"}}

    get_(server=None, secret=False)

    assert mock_http_get.call_count == 1


@mock.patch("deepfellow.server.config_command.get.echo")
@mock.patch("deepfellow.server.config_command.get.http_get")
@mock.patch("deepfellow.server.config_command.get.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.config_command.get.get_server_url", return_value=SERVER)
def test_get_with_secret_flag_reveals_masked_paths(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_http_get.side_effect = [
        {"smtp": {"password": "••••••••", "host": "smtp.example.com"}, "name": "my-server"},
        {"path": "smtp.password", "value": "the-real-secret"},
    ]

    get_(server=None, secret=True)

    assert mock_http_get.call_count == 2
    assert mock_http_get.call_args_list[1] == mock.call(
        f"{SERVER}/admin/config/reveal/smtp.password", "dfuser_abc", item_name="secret value for smtp.password"
    )
    printed = json.loads(mock_echo.info.call_args[0][0])
    assert printed["smtp"]["password"] == "the-real-secret"
    assert printed["smtp"]["host"] == "smtp.example.com"
    assert printed["name"] == "my-server"
