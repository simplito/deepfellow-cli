# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import httpx
import pytest
import typer

from deepfellow.common.state import state
from deepfellow.infra.utils.connection import call_infra, resolve_infra_connection


@pytest.fixture
def config_file() -> Mock:
    return Mock(name="config-file")


@pytest.fixture
def secrets_file() -> Mock:
    m = Mock(spec=Path, name="secrets-file")
    m.is_file.return_value = True
    return m


@pytest.fixture(autouse=True)
def default_state(config_file: Mock, secrets_file: Mock) -> None:
    state.cli_config_file = config_file
    state.cli_secrets_file = secrets_file
    state.cli_config = {}


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.read_env_file")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_resolve_infra_connection_uses_provided_server_and_secrets(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_env_set: Mock,
    config_file: Mock,
    secrets_file: Mock,
) -> None:
    mock_read_env_file.return_value = {"DF_INFRA_ADMIN_API_KEY": "existing-key"}

    server, api_key = resolve_infra_connection("http://infra:8086")

    assert server == "http://infra:8086"
    assert api_key == "existing-key"
    assert mock_read_env_file.call_count == 1
    assert mock_read_env_file.call_args == mock.call(secrets_file)
    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == mock.call(
        config_file, "DF_INFRA_EXTERNAL_URL", "http://infra:8086", should_raise=False
    )
    assert mock_echo.prompt.call_count == 0
    assert mock_echo.prompt_until_valid.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.read_env_file")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_resolve_infra_connection_reuses_matching_config_server(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_env_set: Mock,
    config_file: Mock,
) -> None:
    state.cli_config = {"df_infra_external_url": "http://infra:8086"}
    mock_read_env_file.return_value = {"DF_INFRA_ADMIN_API_KEY": "existing-key"}

    server, api_key = resolve_infra_connection("http://infra:8086")

    assert server == "http://infra:8086"
    assert api_key == "existing-key"
    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.read_env_file")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_resolve_infra_connection_falls_back_to_config_server_when_none_given(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_env_set: Mock,
) -> None:
    state.cli_config = {"df_infra_external_url": "http://config-infra:8086"}
    mock_read_env_file.return_value = {"DF_INFRA_ADMIN_API_KEY": "existing-key"}

    server, api_key = resolve_infra_connection(None)

    assert server == "http://config-infra:8086"
    assert api_key == "existing-key"
    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.read_env_file")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_resolve_infra_connection_prompts_for_server_when_none_available(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_env_set: Mock,
    config_file: Mock,
) -> None:
    mock_echo.prompt_until_valid.return_value = "http://prompted-infra:8086"
    mock_read_env_file.return_value = {"DF_INFRA_ADMIN_API_KEY": "existing-key"}

    server, api_key = resolve_infra_connection(None)

    assert server == "http://prompted-infra:8086"
    assert api_key == "existing-key"
    assert mock_echo.prompt_until_valid.call_count == 1
    assert mock_env_set.call_args == mock.call(
        config_file, "DF_INFRA_EXTERNAL_URL", "http://prompted-infra:8086", should_raise=False
    )


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.read_env_file")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_resolve_infra_connection_prompts_for_api_key_when_secrets_file_missing(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_env_set: Mock,
    secrets_file: Mock,
) -> None:
    secrets_file.is_file.return_value = False
    mock_echo.prompt.return_value = "prompted-key"

    server, api_key = resolve_infra_connection("http://infra:8086")

    assert server == "http://infra:8086"
    assert api_key == "prompted-key"
    assert mock_read_env_file.call_count == 0
    assert mock_echo.prompt.call_count == 1
    assert mock_echo.prompt.call_args == mock.call("Provide Infra Admin API Key", password=True)
    assert mock_env_set.call_args == mock.call(
        secrets_file, "DF_INFRA_ADMIN_API_KEY", "prompted-key", should_raise=False
    )


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.read_env_file")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_resolve_infra_connection_prompts_for_api_key_when_not_in_secrets(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_env_set: Mock,
    secrets_file: Mock,
) -> None:
    mock_read_env_file.return_value = {}
    mock_echo.prompt.return_value = "prompted-key"

    _, api_key = resolve_infra_connection("http://infra:8086")

    assert api_key == "prompted-key"
    assert mock_echo.prompt.call_count == 1
    assert mock_env_set.call_args == mock.call(
        secrets_file, "DF_INFRA_ADMIN_API_KEY", "prompted-key", should_raise=False
    )


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_returns_request_result(mock_echo: Mock) -> None:
    request = Mock(return_value={"status": "OK"})

    result = call_infra(request, "Unable to call Infra")

    assert result == {"status": "OK"}
    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_raises_on_connect_error(mock_echo: Mock) -> None:
    request = Mock(side_effect=httpx.ConnectError("TEST"))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_shows_response_text_on_http_status_error(mock_echo: Mock) -> None:
    response = Mock(text="Service not found")
    request = Mock(side_effect=httpx.HTTPStatusError("TEST", request=Mock(), response=response))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Service not found")


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_shows_default_message_when_response_has_no_body(mock_echo: Mock) -> None:
    response = Mock(text="")
    request = Mock(side_effect=httpx.HTTPStatusError("TEST", request=Mock(), response=response))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to call Infra")
