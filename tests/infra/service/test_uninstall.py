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
from deepfellow.infra.service.uninstall import uninstall


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
    state.cli_config = {"df_infra_external_url": "http://infra:8086"}
    state.cli_config_file = config_file
    state.cli_secrets_file = secrets_file


@mock.patch("deepfellow.infra.utils.connection.echo")
@mock.patch("deepfellow.infra.service.uninstall.make_request")
@mock.patch("deepfellow.infra.service.uninstall.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "test-key"})
def test_uninstall_raises_on_connect_error(
    mock_read_env_file: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.side_effect = httpx.ConnectError("TEST")

    with pytest.raises(typer.Exit):
        uninstall(server=None, name="ollama", purge=False)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )


@mock.patch("deepfellow.infra.service.uninstall.env_set")
@mock.patch("deepfellow.infra.service.uninstall.make_request", return_value={"status": "OK"})
@mock.patch("deepfellow.infra.service.uninstall.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "test-key"})
@mock.patch("deepfellow.infra.service.uninstall.echo")
def test_uninstall_prompts_for_server_until_valid_when_not_configured(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_make_request: Mock,
    mock_env_set: Mock,
) -> None:
    state.cli_config = {}
    mock_echo.prompt_until_valid.return_value = "http://prompted:8086"

    uninstall(server=None, name="ollama", purge=False)

    assert mock_echo.prompt_until_valid.call_count == 1
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.service.uninstall.env_set")
@mock.patch("deepfellow.infra.service.uninstall.make_request", return_value={"status": "OK"})
@mock.patch("deepfellow.infra.service.uninstall.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "test-key"})
@mock.patch("deepfellow.infra.service.uninstall.echo")
def test_uninstall_persists_server_when_changed_from_config(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_make_request: Mock,
    mock_env_set: Mock,
    config_file: Mock,
) -> None:
    uninstall(server="http://new:8086", name="ollama", purge=False)

    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == mock.call(
        config_file, "DF_INFRA_EXTERNAL_URL", "http://new:8086", should_raise=False
    )


@mock.patch("deepfellow.infra.service.uninstall.env_set")
@mock.patch("deepfellow.infra.service.uninstall.make_request", return_value={"status": "OK"})
@mock.patch("deepfellow.infra.service.uninstall.read_env_file", return_value={})
@mock.patch("deepfellow.infra.service.uninstall.echo")
def test_uninstall_prompts_for_api_key_when_missing_from_secrets(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_make_request: Mock,
    mock_env_set: Mock,
    secrets_file: Mock,
) -> None:
    mock_echo.prompt.return_value = "prompted-key"

    uninstall(server="http://infra:8086", name="ollama", purge=False)

    assert mock_echo.prompt.call_count == 1
    assert mock_echo.prompt.call_args == mock.call("Provide Infra Admin API Key", password=True)
    assert mock_env_set.call_args == mock.call(
        secrets_file, "DF_INFRA_ADMIN_API_KEY", "prompted-key", should_raise=False
    )


@mock.patch("deepfellow.infra.service.uninstall.make_request", return_value={"status": "FAILED"})
@mock.patch("deepfellow.infra.service.uninstall.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "test-key"})
@mock.patch("deepfellow.infra.service.uninstall.echo")
def test_uninstall_raises_when_status_not_ok(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_make_request: Mock,
) -> None:
    with pytest.raises(typer.Exit):
        uninstall(server="http://infra:8086", name="ollama", purge=False)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to uninstall service.")
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.service.uninstall.make_request", return_value={"status": "OK"})
@mock.patch("deepfellow.infra.service.uninstall.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "test-key"})
@mock.patch("deepfellow.infra.service.uninstall.echo")
def test_uninstall_success(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_make_request: Mock,
) -> None:
    uninstall(server="http://infra:8086", name="ollama", purge=True)

    assert mock_make_request.call_count == 1
    assert mock_make_request.call_args == mock.call(
        method="DELETE",
        url="http://infra:8086/admin/services/ollama",
        token="test-key",
        data={"purge": True},
        err_msg="Unable to uninstall Service.",
        reraise=True,
    )
    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == mock.call("Service ollama uninstalled.")
