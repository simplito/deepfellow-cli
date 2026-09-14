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

from deepfellow.infra.model.uninstall import uninstall


@mock.patch("deepfellow.infra.utils.connection.echo")
@mock.patch("deepfellow.infra.model.uninstall.make_request")
@mock.patch("deepfellow.infra.model.uninstall.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_uninstall_raises_on_connect_error(
    mock_resolve: Mock,
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


@mock.patch("deepfellow.infra.model.uninstall.make_request", return_value={"status": "OK"})
@mock.patch("deepfellow.infra.model.uninstall.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_uninstall_resolves_connection_and_calls_api_with_resolved_values(
    mock_resolve: Mock,
    mock_make_request: Mock,
) -> None:
    uninstall(server="http://infra:8086", service_name="ollama", model_name="llama-3.1-8B", purge=True)

    assert mock_resolve.call_count == 1
    assert mock_resolve.call_args == mock.call("http://infra:8086")
    assert mock_make_request.call_args == mock.call(
        method="DELETE",
        url="http://infra:8086/admin/services/ollama/models/_?model_id=llama-3.1-8B",
        token="test-key",
        data={"purge": True},
        err_msg="Unable to uninstall Model.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.utils.connection.persist_infra_connection")
@mock.patch("deepfellow.infra.model.uninstall.make_request", return_value={"status": "OK"})
@mock.patch("deepfellow.infra.model.uninstall.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_uninstall_persists_connection_only_after_successful_request(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_persist: Mock,
) -> None:
    uninstall(server="http://infra:8086", service_name="ollama", model_name="llama-3.1-8B", purge=False)

    assert mock_persist.call_count == 1
    assert mock_persist.call_args == mock.call("http://infra:8086", "test-key", quiet=False)


@mock.patch("deepfellow.infra.utils.connection.persist_infra_connection")
@mock.patch("deepfellow.infra.model.uninstall.make_request")
@mock.patch("deepfellow.infra.model.uninstall.resolve_infra_connection", return_value=("http://bad:8086", "bad-key"))
def test_uninstall_does_not_persist_connection_when_request_fails(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_persist: Mock,
) -> None:
    response = Mock(json=Mock(return_value={"error": {"message": "Unauthorized"}}))
    mock_make_request.side_effect = httpx.HTTPStatusError("TEST", request=Mock(), response=response)

    with pytest.raises(typer.Exit):
        uninstall(server="http://bad:8086", service_name="ollama", model_name="llama-3.1-8B", purge=False)

    assert mock_persist.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.persist_infra_connection")
@mock.patch("deepfellow.infra.model.uninstall.echo")
@mock.patch("deepfellow.infra.model.uninstall.make_request", return_value={"status": "FAILED"})
@mock.patch("deepfellow.infra.model.uninstall.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_uninstall_raises_when_status_not_ok(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
    mock_persist: Mock,
) -> None:
    with pytest.raises(typer.Exit):
        uninstall(server="http://infra:8086", service_name="ollama", model_name="llama-3.1-8B", purge=False)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to uninstall model.")
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.persist_infra_connection")
@mock.patch("deepfellow.infra.model.uninstall.echo")
@mock.patch("deepfellow.infra.model.uninstall.make_request", return_value={"status": "OK"})
@mock.patch("deepfellow.infra.model.uninstall.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_uninstall_success(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
    mock_persist: Mock,
) -> None:
    uninstall(server="http://infra:8086", service_name="ollama", model_name="llama-3.1-8B", purge=True)

    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == mock.call("Model llama-3.1-8B uninstalled.")
