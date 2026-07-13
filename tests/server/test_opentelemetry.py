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

from deepfellow.server.opentelemetry import opentelemetry

SERVER = "http://localhost:8000"


@mock.patch("deepfellow.server.opentelemetry.echo")
@mock.patch("deepfellow.server.opentelemetry.make_request")
@mock.patch("deepfellow.server.opentelemetry.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.opentelemetry.get_server_url", return_value=SERVER)
def test_opentelemetry_sends_otel_settings_to_admin_endpoint(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    opentelemetry(otel_url="http://otel-collector:4318", server=None)

    assert mock_make_request.call_count == 1
    assert mock_make_request.call_args == mock.call(
        "PUT",
        f"{SERVER}/admin/config",
        "dfuser_abc",
        data={"otel_exporter_otlp_endpoint": "http://otel-collector:4318", "otel_tracing_enabled": True},
        err_msg="Unable to update server config.",
    )
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.server.opentelemetry.echo")
@mock.patch("deepfellow.server.opentelemetry.make_request")
@mock.patch("deepfellow.server.opentelemetry.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.opentelemetry.get_server_url", return_value=SERVER)
def test_opentelemetry_prompts_for_url_when_omitted(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_echo.prompt_until_valid.return_value = "http://prompted-collector:4318"

    opentelemetry(otel_url=None, server=None)

    assert mock_echo.prompt_until_valid.call_count == 1
    assert mock_make_request.call_args.kwargs["data"]["otel_exporter_otlp_endpoint"] == "http://prompted-collector:4318"


@mock.patch("deepfellow.server.opentelemetry.echo")
@mock.patch("deepfellow.server.opentelemetry.make_request")
@mock.patch("deepfellow.server.opentelemetry.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.opentelemetry.get_server_url", return_value=SERVER)
def test_opentelemetry_calls_echo_info_when_url_still_empty(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_echo.prompt_until_valid.return_value = ""

    opentelemetry(otel_url=None, server=None)

    assert mock_make_request.call_count == 0
    assert mock_echo.info.call_args == (("OpenTelemetry settings in DeepFellow remain the same as before",), {})


@mock.patch("deepfellow.server.opentelemetry.echo")
@mock.patch("deepfellow.server.opentelemetry.make_request")
@mock.patch("deepfellow.server.opentelemetry.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.opentelemetry.get_server_url", return_value=SERVER)
def test_opentelemetry_resolves_token_from_server_url(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    opentelemetry(otel_url="http://otel-collector:4318", server="http://custom-server:9000")

    assert mock_server_url.call_args == mock.call("http://custom-server:9000")
    assert mock_get_token.call_count == 1
    assert mock_get_token.call_args.args[1] == SERVER
