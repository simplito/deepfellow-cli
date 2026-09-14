# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any
from unittest import mock
from unittest.mock import Mock

import httpx
import pytest
import typer

from deepfellow.infra.service.list import _format_service, _is_installed, list


@pytest.mark.parametrize(
    ("service", "expected"),
    [
        ({"installed": False}, False),
        ({"installed": {}}, True),
        ({"installed": {"port": 1234}}, True),
        ({}, False),
    ],
)
def test_is_installed_returns_expected(service: dict[str, Any], expected: bool) -> None:
    result = _is_installed(service)

    assert result is expected


def test_format_service_formats_fields_as_key_value_lines() -> None:
    service = {
        "id": "ollama",
        "type": "llm",
        "instance": "default",
        "description": "Ollama service",
        "downloaded": True,
    }

    result = _format_service(service)

    assert result == "id: ollama\ntype: llm\ninstance: default\ndescription: Ollama service\ndownloaded: True"


@mock.patch("deepfellow.infra.utils.connection.echo")
@mock.patch("deepfellow.infra.service.list.make_request")
@mock.patch("deepfellow.infra.service.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_raises_on_connect_error(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.side_effect = httpx.ConnectError("TEST")

    with pytest.raises(typer.Exit):
        list(server=None)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )


@mock.patch("deepfellow.infra.service.list.make_request", return_value={"list": []})
@mock.patch("deepfellow.infra.service.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_resolves_connection_and_calls_api_with_resolved_values(
    mock_resolve: Mock,
    mock_make_request: Mock,
) -> None:
    list(server="http://infra:8086")

    assert mock_resolve.call_count == 1
    assert mock_resolve.call_args == mock.call("http://infra:8086")
    assert mock_make_request.call_args == mock.call(
        method="GET",
        url="http://infra:8086/admin/services",
        token="test-key",
        err_msg="Unable to list services.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.utils.connection.persist_infra_connection")
@mock.patch("deepfellow.infra.service.list.make_request", return_value={"list": []})
@mock.patch("deepfellow.infra.service.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_persists_connection_only_after_successful_request(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_persist: Mock,
) -> None:
    list(server="http://infra:8086")

    assert mock_persist.call_count == 1
    assert mock_persist.call_args == mock.call("http://infra:8086", "test-key", quiet=False)


@mock.patch("deepfellow.infra.utils.connection.persist_infra_connection")
@mock.patch("deepfellow.infra.service.list.make_request")
@mock.patch("deepfellow.infra.service.list.resolve_infra_connection", return_value=("http://bad:8086", "bad-key"))
def test_list_does_not_persist_connection_when_request_fails(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_persist: Mock,
) -> None:
    response = Mock(json=Mock(return_value={"error": {"message": "Unauthorized"}}))
    mock_make_request.side_effect = httpx.HTTPStatusError("TEST", request=Mock(), response=response)

    with pytest.raises(typer.Exit):
        list(server="http://bad:8086")

    assert mock_persist.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.persist_infra_connection")
@mock.patch("deepfellow.infra.service.list.echo")
@mock.patch("deepfellow.infra.service.list.make_request", return_value={"list": []})
@mock.patch("deepfellow.infra.service.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_prints_no_services_installed_when_list_empty(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
    mock_persist: Mock,
) -> None:
    list(server="http://infra:8086")

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call("No services installed.")


@mock.patch("deepfellow.infra.utils.connection.persist_infra_connection")
@mock.patch("deepfellow.infra.service.list.echo")
@mock.patch(
    "deepfellow.infra.service.list.make_request",
    return_value={
        "list": [
            {
                "id": "ollama",
                "type": "llm",
                "instance": "default",
                "description": "Ollama",
                "downloaded": True,
                "installed": {"port": 1234},
            },
            {"id": "unused", "type": "llm", "installed": False},
        ]
    },
)
@mock.patch("deepfellow.infra.service.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_prints_only_installed_services(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
    mock_persist: Mock,
) -> None:
    list(server="http://infra:8086")

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(
        "id: ollama\ntype: llm\ninstance: default\ndescription: Ollama\ndownloaded: True"
    )
