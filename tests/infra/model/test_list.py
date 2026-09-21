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

from deepfellow.infra.model.list import list as list_command


@mock.patch("deepfellow.infra.utils.connection.echo")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.model.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_raises_on_connect_error(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.side_effect = httpx.ConnectError("TEST")

    with pytest.raises(typer.Exit):
        list_command(server=None, service_name="ollama", installed=None)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )


@mock.patch("deepfellow.infra.model.list.echo")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.model.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_resolves_connection_and_calls_api_with_resolved_values(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.return_value = {"list": []}

    list_command(server="http://infra:8086", service_name="ollama", installed=None)

    assert mock_resolve.call_count == 1
    assert mock_resolve.call_args == mock.call("http://infra:8086")
    assert mock_make_request.call_args == mock.call(
        method="GET",
        url="http://infra:8086/admin/services/ollama/models",
        token="test-key",
        err_msg="Unable to list models for service 'ollama'.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.model.list.echo")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.model.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_forwards_installed_true_as_a_query_filter(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.return_value = {"list": []}

    list_command(server=None, service_name="ollama", installed=True)

    assert mock_make_request.call_args == mock.call(
        method="GET",
        url="http://infra:8086/admin/services/ollama/models?installed=true",
        token="test-key",
        err_msg="Unable to list models for service 'ollama'.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.model.list.echo")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.model.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_forwards_installed_false_as_a_query_filter(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.return_value = {"list": []}

    list_command(server=None, service_name="ollama", installed=False)

    assert mock_make_request.call_args == mock.call(
        method="GET",
        url="http://infra:8086/admin/services/ollama/models?installed=false",
        token="test-key",
        err_msg="Unable to list models for service 'ollama'.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.model.list.echo")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.model.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_omits_installed_query_filter_by_default(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.return_value = {"list": []}

    list_command(server=None, service_name="ollama", installed=None)

    assert mock_make_request.call_args == mock.call(
        method="GET",
        url="http://infra:8086/admin/services/ollama/models",
        token="test-key",
        err_msg="Unable to list models for service 'ollama'.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.model.list.echo")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.model.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_prints_installed_and_not_installed_models(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.return_value = {
        "list": [
            {"id": "llama-3.1-8B", "type": "ollama", "size": "4.7GB", "installed": True},
            {"id": "llama-3.1-70B", "type": "ollama", "size": "40GB", "installed": False, "description": "Big model."},
        ]
    }

    list_command(server=None, service_name="ollama", installed=None)

    assert mock_echo.info.call_count == 1
    printed = mock_echo.info.call_args[0][0]
    assert "id: llama-3.1-8B" in printed
    assert "installed: True" in printed
    assert "id: llama-3.1-70B" in printed
    assert "installed: False" in printed
    assert "description: Big model." in printed


@mock.patch("deepfellow.infra.model.list.echo")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.model.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_prints_info_message_when_no_models_available(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.return_value = {"list": []}

    list_command(server=None, service_name="ollama", installed=None)

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call("No models available.")
    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.echo")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.model.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_raises_on_unknown_service(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    response = Mock(json=Mock(return_value={"error": {"message": "Service 'unknown' not found"}}))
    mock_make_request.side_effect = httpx.HTTPStatusError("TEST", request=Mock(), response=response)

    with pytest.raises(typer.Exit):
        list_command(server=None, service_name="unknown", installed=None)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Service 'unknown' not found")
