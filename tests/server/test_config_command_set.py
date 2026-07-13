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

from deepfellow.server.config_command.set import set_

SERVER = "http://localhost:8000"


@mock.patch("deepfellow.server.config_command.set.echo")
@mock.patch("deepfellow.server.config_command.set.make_request")
@mock.patch("deepfellow.server.config_command.set.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.config_command.set.get_server_url", return_value=SERVER)
def test_set_sends_parsed_updates_to_admin_endpoint(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.return_value = {"otel_tracing_enabled": True}

    set_(updates=["otel_tracing_enabled=true"], server=None)

    assert mock_make_request.call_count == 1
    assert mock_make_request.call_args == mock.call(
        "PUT",
        f"{SERVER}/admin/config",
        "dfuser_abc",
        data={"otel_tracing_enabled": True},
        err_msg="Unable to update server config.",
    )
    assert mock_echo.success.call_count == 1
    assert mock_echo.info.call_count == 1


@mock.patch("deepfellow.server.config_command.set.echo")
@mock.patch("deepfellow.server.config_command.set.http_get")
@mock.patch("deepfellow.server.config_command.set.make_request")
@mock.patch("deepfellow.server.config_command.set.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.config_command.set.get_server_url", return_value=SERVER)
def test_set_without_secret_flag_does_not_reveal(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_make_request: Mock,
    mock_http_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.return_value = {"smtp": {"password": "••••••••"}}

    set_(updates=["smtp_password=foo"], server=None, secret=False)

    assert mock_make_request.call_count == 1
    assert mock_http_get.call_count == 0


@mock.patch("deepfellow.server.config_command.set.echo")
@mock.patch("deepfellow.server.config_command.set.http_get")
@mock.patch("deepfellow.server.config_command.set.make_request")
@mock.patch("deepfellow.server.config_command.set.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.config_command.set.get_server_url", return_value=SERVER)
def test_set_with_secret_flag_reveals_masked_paths(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_make_request: Mock,
    mock_http_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.return_value = {"smtp": {"password": "••••••••"}, "name": "my-server"}
    mock_http_get.return_value = {"path": "smtp.password", "value": "the-real-secret"}

    set_(updates=["smtp_password=foo"], server=None, secret=True)

    assert mock_http_get.call_count == 1
    assert mock_http_get.call_args == mock.call(
        f"{SERVER}/admin/config/reveal/smtp.password", "dfuser_abc", item_name="secret value for smtp.password"
    )
    printed = json.loads(mock_echo.info.call_args[0][0])
    assert printed["smtp"]["password"] == "the-real-secret"
    assert printed["name"] == "my-server"
