# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

import ssl
from collections.abc import Iterator
from unittest import mock
from unittest.mock import Mock

import httpx
import pytest

from deepfellow.workspace.utils.server import _failed, is_server_reachable, list_server_models, resolve_server_ids


def _response(status_code: int, payload: object) -> httpx.Response:
    return httpx.Response(status_code, json=payload, request=httpx.Request("GET", "https://df.example.com/info"))


@pytest.mark.parametrize(
    "server_url", ["https://df.example.com/v1", "https://df.example.com/v1/", "https://df.example.com"]
)
@mock.patch("deepfellow.workspace.utils.server.httpx.get")
def test_resolve_server_ids_returns_ids_from_root_info_endpoint(mock_get: Mock, server_url: str) -> None:
    mock_get.return_value = _response(200, {"organization_id": "org", "project_id": "proj"})

    result = resolve_server_ids(server_url, "key")

    assert result == ("org", "proj")
    assert mock_get.call_count == 1
    assert mock_get.call_args == mock.call(
        "https://df.example.com/info", headers={"Authorization": "Bearer key"}, timeout=5.0
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"version": "0.37.0"},
        {"organization_id": "org", "project_id": None},
        {"organization_id": None, "project_id": None},
        ["x"],
    ],
)
@mock.patch("deepfellow.workspace.utils.server.httpx.get")
def test_resolve_server_ids_returns_none_when_server_does_not_report_both_ids(mock_get: Mock, payload: object) -> None:
    mock_get.return_value = _response(200, payload)

    result = resolve_server_ids("https://df.example.com/v1", "key")

    assert result is None


@mock.patch("deepfellow.workspace.utils.server.httpx.get")
def test_resolve_server_ids_returns_none_when_server_rejects_the_key(mock_get: Mock) -> None:
    mock_get.return_value = _response(401, {"detail": "Unauthorized"})

    result = resolve_server_ids("https://df.example.com/v1", "key")

    assert result is None


@mock.patch("deepfellow.workspace.utils.server.httpx.get", side_effect=httpx.ConnectError("down"))
def test_resolve_server_ids_returns_none_when_server_is_unreachable(mock_get: Mock) -> None:
    result = resolve_server_ids("https://df.example.com/v1", "key")

    assert result is None


@pytest.mark.parametrize(
    "server_url", ["https://df.example.com/v1", "https://df.example.com/v1/", "https://df.example.com"]
)
@mock.patch("deepfellow.workspace.utils.server.httpx.get")
def test_list_server_models_returns_unique_ids_from_models_endpoint(mock_get: Mock, server_url: str) -> None:
    mock_get.return_value = _response(200, {"data": [{"id": "a"}, {"id": "b"}, {"id": "a"}, {"name": "x"}, "y"]})

    result = list_server_models(server_url, "key")

    assert result == ["a", "b"]
    assert mock_get.call_args == mock.call(
        "https://df.example.com/v1/models?additional_data=true", headers={"Authorization": "Bearer key"}, timeout=5.0
    )


@mock.patch("deepfellow.workspace.utils.server.httpx.get")
def test_list_server_models_keeps_only_chat_models(mock_get: Mock) -> None:
    types = ["llm", "embedding", "stt", "tts", "rerank", "decision", "mcp-sse", "custom", "llm-vision", ""]
    mock_get.return_value = _response(
        200, {"data": [{"id": f"m{i}", "props": {"type": kind}} for i, kind in enumerate(types)]}
    )

    result = list_server_models("https://df.example.com/v1", "key")

    assert result == ["m0", "m8", "m9"]


@mock.patch("deepfellow.workspace.utils.server.httpx.get")
def test_list_server_models_keeps_models_without_props(mock_get: Mock) -> None:
    mock_get.return_value = _response(
        200, {"data": [{"id": "a"}, {"id": "b", "props": None}, {"id": "c", "props": {}}]}
    )

    result = list_server_models("https://df.example.com/v1", "key")

    assert result == ["a", "b", "c"]


@pytest.mark.parametrize("payload", [{"version": "1"}, {"data": "x"}, ["x"]])
@mock.patch("deepfellow.workspace.utils.server.httpx.get")
def test_list_server_models_returns_none_for_unexpected_payload(mock_get: Mock, payload: object) -> None:
    mock_get.return_value = _response(200, payload)

    assert list_server_models("https://df.example.com/v1", "key") is None


@mock.patch("deepfellow.workspace.utils.server.httpx.get")
def test_list_server_models_returns_none_when_server_rejects_the_key(mock_get: Mock) -> None:
    mock_get.return_value = _response(401, {"detail": "Unauthorized"})

    assert list_server_models("https://df.example.com/v1", "key") is None


@mock.patch("deepfellow.workspace.utils.server.httpx.get", side_effect=httpx.ConnectError("down"))
def test_list_server_models_returns_none_when_server_is_unreachable(mock_get: Mock) -> None:
    assert list_server_models("https://df.example.com/v1", "key") is None


@mock.patch("deepfellow.workspace.utils.server.httpx.get", side_effect=httpx.InvalidURL("bad url"))
def test_list_server_models_returns_none_for_invalid_url(mock_get: Mock) -> None:
    assert list_server_models("https://df.example.com/v1", "key") is None


@mock.patch("deepfellow.workspace.utils.server.httpx.get", side_effect=httpx.InvalidURL("bad url"))
def test_resolve_server_ids_returns_none_for_invalid_url(mock_get: Mock) -> None:
    assert resolve_server_ids("https://df.example.com/v1", "key") is None


@mock.patch("deepfellow.workspace.utils.server.echo")
@mock.patch("deepfellow.workspace.utils.server.httpx.get")
def test_resolve_server_ids_warns_with_rejected_key_reason(mock_get: Mock, mock_echo: Mock) -> None:
    mock_get.return_value = _response(401, {})

    result = resolve_server_ids("https://df.example.com/v1", "key")

    assert result is None
    assert mock_echo.warning.call_args == mock.call(
        "Request to DeepFellow Server failed (GET https://df.example.com/info): HTTP 401 - the API key was rejected"
    )


@mock.patch("deepfellow.workspace.utils.server.echo")
@mock.patch("deepfellow.workspace.utils.server.httpx.get", side_effect=httpx.ReadTimeout("slow"))
def test_list_server_models_warns_with_timeout_reason(mock_get: Mock, mock_echo: Mock) -> None:
    result = list_server_models("https://df.example.com/v1", "key")

    assert result is None
    assert mock_echo.warning.call_args == mock.call(
        "Request to DeepFellow Server failed (GET https://df.example.com/v1/models?additional_data=true): "
        "timed out after 5s"
    )


@mock.patch("deepfellow.workspace.utils.server.echo")
@mock.patch("deepfellow.workspace.utils.server.httpx.get", side_effect=httpx.ConnectError(""))
def test_resolve_server_ids_warns_with_exception_type_when_message_is_empty(mock_get: Mock, mock_echo: Mock) -> None:
    resolve_server_ids("https://df.example.com/v1", "key")

    assert mock_echo.warning.call_args.args[0].endswith("ConnectError")


@mock.patch("deepfellow.workspace.utils.server.echo")
@mock.patch("deepfellow.workspace.utils.server.httpx.get", side_effect=httpx.ConnectError("refused"))
def test_resolve_server_ids_warns_with_exception_message(mock_get: Mock, mock_echo: Mock) -> None:
    resolve_server_ids("https://df.example.com/v1", "key")

    assert mock_echo.warning.call_args.args[0].endswith("refused")


@pytest.fixture(autouse=True)
def _reset_failed() -> Iterator[None]:
    _failed.clear()
    yield
    _failed.clear()


@mock.patch("deepfellow.workspace.utils.server.echo")
@mock.patch("deepfellow.workspace.utils.server.httpx.get", side_effect=httpx.ConnectError("refused"))
def test_server_lookups_warn_and_request_once_for_unreachable_server(mock_get: Mock, mock_echo: Mock) -> None:
    resolve_server_ids("https://df.example.com/v1", "key")
    list_server_models("https://df.example.com/v1", "key")

    assert mock_get.call_count == 1
    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.workspace.utils.server.state")
@mock.patch("deepfellow.workspace.utils.server.httpx.get")
def test_resolve_server_ids_falls_back_to_host_url_from_cli_config(mock_get: Mock, mock_state: Mock) -> None:
    mock_state.cli_config = {"df_server_url": "http://localhost:8000"}
    mock_get.side_effect = [
        httpx.ConnectError("no such host"),
        _response(200, {"organization_id": "o", "project_id": "p"}),
    ]

    result = resolve_server_ids("http://server:8000/v1", "key")

    assert result == ("o", "p")
    assert mock_get.call_args.args == ("http://localhost:8000/info",)


@mock.patch("deepfellow.workspace.utils.server.state")
@mock.patch("deepfellow.workspace.utils.server.httpx.get")
def test_is_server_reachable_remote_url_answers_returns_true(mock_get: Mock, mock_state: Mock) -> None:
    mock_state.cli_config = {}
    mock_get.return_value = _response(404, {})

    assert is_server_reachable("https://df.example.com/v1") is True
    assert mock_get.call_args == mock.call("https://df.example.com", timeout=5.0)


@mock.patch("deepfellow.workspace.utils.server.state")
@mock.patch("deepfellow.workspace.utils.server.httpx.get", side_effect=httpx.ConnectError("refused"))
def test_is_server_reachable_connection_refused_returns_false(mock_get: Mock, mock_state: Mock) -> None:
    mock_state.cli_config = {}

    assert is_server_reachable("https://df.example.com/v1") is False


@mock.patch("deepfellow.workspace.utils.server.state")
@mock.patch("deepfellow.workspace.utils.server.httpx.get")
def test_is_server_reachable_container_url_down_falls_back_to_host_url(mock_get: Mock, mock_state: Mock) -> None:
    mock_state.cli_config = {"df_server_url": "http://localhost:8000"}
    mock_get.side_effect = [httpx.ConnectError("no such host"), _response(200, {})]

    assert is_server_reachable("http://server:8000/v1") is True
    assert mock_get.call_count == 2
    assert mock_get.call_args == mock.call("http://localhost:8000", timeout=5.0)


@mock.patch("deepfellow.workspace.utils.server.state")
@mock.patch("deepfellow.workspace.utils.server.httpx.get")
def test_is_server_reachable_untrusted_certificate_returns_true(mock_get: Mock, mock_state: Mock) -> None:
    # Arrange
    mock_state.cli_config = {}
    error = httpx.ConnectError("certificate verify failed")
    error.__cause__ = ssl.SSLCertVerificationError("self-signed certificate")
    mock_get.side_effect = error

    # Act
    result = is_server_reachable("https://df.example.com/v1")

    # Assert
    assert result is True
