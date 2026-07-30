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

import httpx
import pytest
import typer

from deepfellow.infra.model.install import install as install_command
from deepfellow.infra.utils.model_install import install


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_raises_on_connect_error(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_install_with_progress.side_effect = httpx.ConnectError("TEST")

    with pytest.raises(typer.Exit):
        install(server=None, service_name="ollama", model_name="llama-3.1-8B")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.model_install.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_success(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_install_with_progress.return_value = {"status": "OK"}

    install(server=None, service_name="ollama", model_name="llama-3.1-8B")

    assert mock_install_with_progress.call_count == 1
    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == mock.call("Model llama-3.1-8B installed.")


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.model_install.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_raises_when_status_not_ok(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_install_with_progress.return_value = {"status": "FAILED"}

    with pytest.raises(typer.Exit):
        install(server=None, service_name="ollama", model_name="llama-3.1-8B")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to install model.")


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.model_install.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_exits_with_detail_when_finish_status_error(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_install_with_progress.return_value = {"type": "finish", "status": "error", "detail": "out of memory"}

    with pytest.raises(typer.Exit):
        install(server="http://infra:8086", service_name="ollama", model_name="llama-3.1-8B")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to install model. out of memory")
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.model.install.install_util")
def test_install_command_delegates_to_install_util(mock_install_util: Mock) -> None:
    install_command(server="http://infra:8086", service_name="ollama", model_name="llama-3.1-8B")

    assert mock_install_util.call_count == 1
    assert mock_install_util.call_args == mock.call(
        service_name="ollama", model_name="llama-3.1-8B", server="http://infra:8086"
    )
