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
from deepfellow.infra.model.uninstall import uninstall


@pytest.fixture
def secrets_file() -> Mock:
    m = Mock(spec=Path, name="secrets-file")
    m.is_file.return_value = True
    return m


@pytest.fixture(autouse=True)
def default_state(secrets_file: Mock) -> None:
    state.cli_config = {"df_infra_external_url": "http://infra:8086"}
    state.cli_secrets_file = secrets_file


@mock.patch("deepfellow.infra.utils.connection.echo")
@mock.patch("deepfellow.infra.model.uninstall.make_request")
@mock.patch("deepfellow.infra.model.uninstall.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "test-key"})
def test_uninstall_raises_on_connect_error(
    mock_read_env_file: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.side_effect = httpx.ConnectError("TEST")

    with pytest.raises(typer.Exit):
        uninstall(server=None, service_name="ollama", model_name="llama-3.1-8B", purge=False)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )
