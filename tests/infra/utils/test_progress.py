# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from typing import Any
from unittest import mock
from unittest.mock import Mock

import httpx
import pytest

from deepfellow.infra.utils.progress import install_with_progress


def _sse_lines(*events: dict[str, Any]) -> list[str]:
    return [json.dumps(event) for event in events]


def _stream_response(
    *,
    status_code: int = 200,
    content_type: str = "text/event-stream",
    lines: list[str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Mock:
    response = Mock(name="response")
    response.status_code = status_code
    response.headers = {"content-type": content_type}
    response.iter_lines.return_value = lines or []
    response.json.return_value = json_body or {}
    response.request = Mock(name="request")
    return response


@mock.patch("deepfellow.infra.utils.progress.Progress")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=True)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_returns_finish_on_successful_sse(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_progress: Mock,
) -> None:
    response = _stream_response(
        lines=_sse_lines(
            {"type": "progress", "stage": "download", "value": 0.5},
            {"type": "progress", "stage": "download", "value": 1.0},
            {"type": "finish", "status": "ok"},
        )
    )
    mock_stream.return_value.__enter__.return_value = response

    result = install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert result == {"type": "finish", "status": "ok"}
    assert response.iter_lines.call_count == 1


@mock.patch("deepfellow.infra.utils.progress.Progress")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=True)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_returns_error_finish_on_failed_sse(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_progress: Mock,
) -> None:
    response = _stream_response(
        lines=_sse_lines(
            {"type": "progress", "stage": "install", "value": 0.2},
            {"type": "finish", "status": "error", "detail": "disk full"},
        )
    )
    mock_stream.return_value.__enter__.return_value = response

    result = install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert result == {"type": "finish", "status": "error", "detail": "disk full"}


@mock.patch("deepfellow.infra.utils.progress.Progress")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=True)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_parses_data_prefixed_sse_lines(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_progress: Mock,
) -> None:
    response = _stream_response(
        lines=[
            "",
            "data: " + json.dumps({"type": "progress", "stage": "download", "value": 0.5}),
            "data: " + json.dumps({"type": "finish", "status": "ok"}),
        ]
    )
    mock_stream.return_value.__enter__.return_value = response

    result = install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert result == {"type": "finish", "status": "ok"}


@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_falls_back_to_plain_json_when_not_event_stream(
    mock_stream: Mock,
) -> None:
    response = _stream_response(content_type="application/json", json_body={"status": "OK"})
    mock_stream.return_value.__enter__.return_value = response

    result = install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert result == {"status": "OK"}
    assert response.iter_lines.call_count == 0


@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_injects_stream_true_in_request_body(
    mock_stream: Mock,
) -> None:
    response = _stream_response(content_type="application/json", json_body={"status": "OK"})
    mock_stream.return_value.__enter__.return_value = response

    install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {"hardware": "GPU"}})

    assert mock_stream.call_count == 1
    assert mock_stream.call_args.kwargs["json"] == {"spec": {"hardware": "GPU"}, "stream": True}


@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_logs_periodic_progress_when_non_interactive(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
) -> None:
    response = _stream_response(
        lines=_sse_lines(
            {"type": "progress", "stage": "download", "value": 0.0},
            {"type": "progress", "stage": "download", "value": 0.5},
            {"type": "finish", "status": "ok"},
        )
    )
    mock_stream.return_value.__enter__.return_value = response

    result = install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert result == {"type": "finish", "status": "ok"}
    assert mock_echo.info.call_count == 2
    assert mock_echo.info.call_args_list == [mock.call("download: 0%"), mock.call("download: 50%")]


@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_skips_non_json_stream_lines(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
) -> None:
    response = _stream_response(
        lines=[
            "not json",
            json.dumps({"type": "progress", "stage": "download", "value": 0.5}),
            json.dumps({"type": "finish", "status": "ok"}),
        ]
    )
    mock_stream.return_value.__enter__.return_value = response

    result = install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert result == {"type": "finish", "status": "ok"}
    assert mock.call("Skipping non-JSON stream line: 'not json'") in mock_echo.debug.call_args_list


@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_raises_http_status_error_on_client_error(
    mock_stream: Mock,
) -> None:
    response = _stream_response(status_code=403)
    mock_stream.return_value.__enter__.return_value = response

    with pytest.raises(httpx.HTTPStatusError):
        install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert response.read.call_count == 1


@mock.patch("deepfellow.infra.utils.progress.Progress")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=True)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_returns_default_finish_when_stream_ends_without_finish_event(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_progress: Mock,
) -> None:
    response = _stream_response(lines=[])
    mock_stream.return_value.__enter__.return_value = response

    result = install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert result == {"type": "finish", "status": "error"}


@mock.patch("deepfellow.infra.utils.progress.Progress")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=True)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_ignores_unknown_event_type_when_interactive(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_progress: Mock,
) -> None:
    response = _stream_response(
        lines=_sse_lines(
            {"type": "unknown"},
            {"type": "finish", "status": "ok"},
        )
    )
    mock_stream.return_value.__enter__.return_value = response

    result = install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert result == {"type": "finish", "status": "ok"}


@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_returns_default_finish_when_stream_ends_without_finish_event_non_interactive(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
) -> None:
    response = _stream_response(lines=[])
    mock_stream.return_value.__enter__.return_value = response

    result = install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert result == {"type": "finish", "status": "error"}
    assert mock_echo.info.call_count == 0


@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_skips_progress_log_below_step_threshold_when_non_interactive(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
) -> None:
    response = _stream_response(
        lines=_sse_lines(
            {"type": "progress", "stage": "download", "value": 0.5},
            {"type": "progress", "stage": "download", "value": 0.55},
            {"type": "finish", "status": "ok"},
        )
    )
    mock_stream.return_value.__enter__.return_value = response

    result = install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert result == {"type": "finish", "status": "ok"}
    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call("download: 50%")


@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_ignores_unknown_event_type_when_non_interactive(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
) -> None:
    response = _stream_response(
        lines=_sse_lines(
            {"type": "unknown"},
            {"type": "finish", "status": "ok"},
        )
    )
    mock_stream.return_value.__enter__.return_value = response

    result = install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert result == {"type": "finish", "status": "ok"}
    assert mock_echo.info.call_count == 0
