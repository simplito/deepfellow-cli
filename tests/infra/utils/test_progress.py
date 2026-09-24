# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from collections.abc import Iterator
from typing import Any
from unittest import mock
from unittest.mock import Mock

import httpx
import pytest

from deepfellow.infra.utils.progress import _Heartbeat, _StageOnlyColumn, install_with_progress


def _sse_lines(*events: dict[str, Any]) -> list[str]:
    return [json.dumps(event) for event in events]


def _lines_then_read_error(*lines: str) -> Iterator[str]:
    """Yield SSE lines, then fail the stream the way a dropped connection would."""
    yield from lines
    raise httpx.ReadError("connection dropped")


def _stream_response(
    *,
    status_code: int = 200,
    content_type: str = "text/event-stream",
    lines: list[str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Mock:
    response = Mock(name="response")
    response.status_code = status_code
    response.is_error = status_code >= 400
    response.headers = {"content-type": content_type}
    response.iter_lines.return_value = lines or []
    response.json.return_value = json_body or {}
    response.request = Mock(name="request")
    if response.is_error:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status_code}", request=response.request, response=response
        )
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


@mock.patch("deepfellow.infra.utils.progress._Heartbeat")
@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_logs_periodic_progress_when_non_interactive(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_heartbeat: Mock,
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


@mock.patch("deepfellow.infra.utils.progress._Heartbeat")
@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_skips_non_json_stream_lines(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_heartbeat: Mock,
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


@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_reads_body_on_server_error_before_raising(
    mock_stream: Mock,
) -> None:
    # Regression test: any error status - not only 400/401/403 - must have its body read while
    # still inside the `httpx.stream` context, or `call_infra` crashes with `ResponseNotRead`
    # trying to extract a message from the now-closed response.
    response = _stream_response(status_code=422, json_body={"detail": "prefix already in use"})
    mock_stream.return_value.__enter__.return_value = response

    with pytest.raises(httpx.HTTPStatusError):
        install_with_progress("http://infra:8086/admin/services/mcp/models/_", "test-key", data={"spec": {}})

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


@mock.patch("deepfellow.infra.utils.progress._Heartbeat")
@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_skips_progress_log_below_step_threshold_when_non_interactive(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_heartbeat: Mock,
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


@mock.patch("deepfellow.infra.utils.progress._Heartbeat")
@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_notifies_heartbeat_of_unfinished_stage_when_non_interactive(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_heartbeat: Mock,
) -> None:
    response = _stream_response(
        lines=_sse_lines(
            {"type": "progress", "stage": "install", "value": 0.0},
            {"type": "finish", "status": "ok"},
        )
    )
    mock_stream.return_value.__enter__.return_value = response

    result = install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert result == {"type": "finish", "status": "ok"}
    assert mock_heartbeat.call_count == 1
    assert mock_heartbeat.return_value.start.call_count == 1
    assert mock_heartbeat.return_value.notify.call_args_list == [mock.call("install")]


@mock.patch("deepfellow.infra.utils.progress._Heartbeat")
@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_stops_heartbeat_after_finish_event(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_heartbeat: Mock,
) -> None:
    response = _stream_response(
        lines=_sse_lines(
            {"type": "progress", "stage": "install", "value": 0.0},
            {"type": "finish", "status": "ok"},
        )
    )
    mock_stream.return_value.__enter__.return_value = response

    install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert mock_heartbeat.return_value.stop.call_count == 1


@mock.patch("deepfellow.infra.utils.progress._Heartbeat")
@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_notifies_heartbeat_on_each_progress_event(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_heartbeat: Mock,
) -> None:
    response = _stream_response(
        lines=_sse_lines(
            {"type": "progress", "stage": "download", "value": 0.0},
            {"type": "progress", "stage": "download", "value": 0.5},
            {"type": "finish", "status": "ok"},
        )
    )
    mock_stream.return_value.__enter__.return_value = response

    install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert mock_heartbeat.call_count == 1
    assert mock_heartbeat.return_value.start.call_count == 1
    assert mock_heartbeat.return_value.notify.call_args_list == [mock.call("download"), mock.call("download")]


@mock.patch("deepfellow.infra.utils.progress._Heartbeat")
@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_clears_heartbeat_stage_for_completed_stage(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_heartbeat: Mock,
) -> None:
    response = _stream_response(
        lines=_sse_lines(
            {"type": "progress", "stage": "install", "value": 1.0},
            {"type": "finish", "status": "ok"},
        )
    )
    mock_stream.return_value.__enter__.return_value = response

    install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert mock_heartbeat.return_value.notify.call_args_list == [mock.call(None)]
    assert mock_echo.info.call_args == mock.call("install: 100%")


@mock.patch("deepfellow.infra.utils.progress._Heartbeat")
@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_stops_heartbeat_when_stream_fails_before_finish(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_heartbeat: Mock,
) -> None:
    response = _stream_response()
    response.iter_lines.return_value = _lines_then_read_error(
        json.dumps({"type": "progress", "stage": "install", "value": 0.0})
    )
    mock_stream.return_value.__enter__.return_value = response

    with pytest.raises(httpx.ReadError):
        install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert mock_heartbeat.return_value.stop.call_count == 1


@mock.patch("deepfellow.infra.utils.progress.Progress")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=True)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_adds_indeterminate_task_for_zero_value_stage(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_progress: Mock,
) -> None:
    response = _stream_response(
        lines=_sse_lines(
            {"type": "progress", "stage": "install", "value": 0.0},
            {"type": "finish", "status": "error"},
        )
    )
    mock_stream.return_value.__enter__.return_value = response
    progress_instance = mock_progress.return_value.__enter__.return_value
    progress_instance.add_task.side_effect = ["main-task", "stage-task"]

    install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert progress_instance.add_task.call_count == 2
    assert progress_instance.add_task.call_args_list == [
        mock.call("Installing...", total=None, header=True),
        mock.call("Install…", total=None),
    ]
    assert progress_instance.update.call_args_list == [mock.call("stage-task", completed=0.0, total=None)]


@mock.patch("deepfellow.infra.utils.progress.Progress")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=True)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_promotes_task_to_determinate_on_first_real_value(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_progress: Mock,
) -> None:
    response = _stream_response(
        lines=_sse_lines(
            {"type": "progress", "stage": "download", "value": 0.0},
            {"type": "progress", "stage": "download", "value": 0.5},
            {"type": "finish", "status": "error"},
        )
    )
    mock_stream.return_value.__enter__.return_value = response
    progress_instance = mock_progress.return_value.__enter__.return_value
    progress_instance.add_task.side_effect = ["main-task", "stage-task"]

    install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert progress_instance.add_task.call_count == 2
    assert progress_instance.update.call_args_list == [
        mock.call("stage-task", completed=0.0, total=None),
        mock.call("stage-task", completed=0.5, total=1.0),
    ]


@mock.patch("deepfellow.infra.utils.progress.Progress")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=True)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_snaps_indeterminate_task_to_full_on_success(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_progress: Mock,
) -> None:
    response = _stream_response(
        lines=_sse_lines(
            {"type": "progress", "stage": "install", "value": 0.0},
            {"type": "finish", "status": "ok"},
        )
    )
    mock_stream.return_value.__enter__.return_value = response
    progress_instance = mock_progress.return_value.__enter__.return_value
    progress_instance.add_task.side_effect = ["main-task", "stage-task"]

    install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert progress_instance.update.call_args_list == [
        mock.call("stage-task", completed=0.0, total=None),
        mock.call("main-task", total=1.0, completed=1.0),
        mock.call("stage-task", total=1.0, completed=1.0),
    ]


@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.threading.Event")
@mock.patch("deepfellow.infra.utils.progress.threading.Thread")
def test_heartbeat_prints_line_per_interval_of_uninterrupted_silence(
    mock_thread: Mock,
    mock_event: Mock,
    mock_echo: Mock,
) -> None:
    mock_event.return_value.wait.side_effect = [False] * 7 + [True]
    mock_event.return_value.is_set.return_value = False
    heartbeat = _Heartbeat(interval=3.0, poll=1.0)
    heartbeat.notify("install")

    heartbeat._run()

    assert mock_echo.info.call_args_list == [
        mock.call("install: still working… (3s)"),
        mock.call("install: still working… (6s)"),
    ]


@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.threading.Event")
@mock.patch("deepfellow.infra.utils.progress.threading.Thread")
def test_heartbeat_prints_nothing_while_silence_stays_below_interval(
    mock_thread: Mock,
    mock_event: Mock,
    mock_echo: Mock,
) -> None:
    mock_event.return_value.wait.side_effect = [False, False, True]
    mock_event.return_value.is_set.return_value = False
    heartbeat = _Heartbeat(interval=3.0, poll=1.0)
    heartbeat.notify("install")

    heartbeat._run()

    assert mock_echo.info.call_count == 0


@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.threading.Event")
@mock.patch("deepfellow.infra.utils.progress.threading.Thread")
def test_heartbeat_prints_nothing_when_no_stage_is_in_flight(
    mock_thread: Mock,
    mock_event: Mock,
    mock_echo: Mock,
) -> None:
    mock_event.return_value.wait.side_effect = [False] * 7 + [True]
    mock_event.return_value.is_set.return_value = False
    heartbeat = _Heartbeat(interval=3.0, poll=1.0)
    heartbeat.notify(None)

    heartbeat._run()

    assert mock_echo.info.call_count == 0


@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.threading.Event")
@mock.patch("deepfellow.infra.utils.progress.threading.Thread")
def test_heartbeat_notify_restarts_the_silence_countdown(
    mock_thread: Mock,
    mock_event: Mock,
    mock_echo: Mock,
) -> None:
    heartbeat = _Heartbeat(interval=3.0, poll=1.0)
    heartbeat.notify("download")
    ticks = {"count": 0}

    def wait(timeout: float) -> bool:
        ticks["count"] += 1
        if ticks["count"] == 2:
            # A progress event lands one second before the first line would be due.
            heartbeat.notify("download")
        return ticks["count"] > 5

    mock_event.return_value.wait.side_effect = wait
    mock_event.return_value.is_set.return_value = False

    heartbeat._run()

    # Without the reset the worker would have printed at 3s and 6s of wall time.
    assert mock_echo.info.call_args_list == [mock.call("download: still working… (3s)")]


@mock.patch("deepfellow.infra.utils.progress.echo")
@mock.patch("deepfellow.infra.utils.progress.threading.Event")
@mock.patch("deepfellow.infra.utils.progress.threading.Thread")
def test_heartbeat_prints_nothing_when_stopped_while_the_line_was_due(
    mock_thread: Mock,
    mock_event: Mock,
    mock_echo: Mock,
) -> None:
    # wait() timed out, but stop() set the flag before the worker took the lock.
    mock_event.return_value.wait.side_effect = [False, True]
    mock_event.return_value.is_set.return_value = True
    heartbeat = _Heartbeat(interval=1.0, poll=1.0)
    heartbeat.notify("install")

    heartbeat._run()

    assert mock_echo.info.call_count == 0


@mock.patch("deepfellow.infra.utils.progress.threading.Thread")
def test_heartbeat_start_runs_worker_in_named_daemon_thread(mock_thread: Mock) -> None:
    heartbeat = _Heartbeat()

    heartbeat.start()

    assert mock_thread.call_count == 1
    assert mock_thread.call_args.kwargs["name"] == "heartbeat"
    assert mock_thread.call_args.kwargs["daemon"] is True
    assert mock_thread.return_value.start.call_count == 1


@mock.patch("deepfellow.infra.utils.progress.threading.Event")
@mock.patch("deepfellow.infra.utils.progress.threading.Thread")
def test_heartbeat_stop_signals_worker_and_joins_running_thread(
    mock_thread: Mock,
    mock_event: Mock,
) -> None:
    mock_thread.return_value.is_alive.return_value = True
    heartbeat = _Heartbeat()
    heartbeat.start()

    heartbeat.stop()

    assert mock_event.return_value.set.call_count == 1
    assert mock_thread.return_value.join.call_count == 1


@mock.patch("deepfellow.infra.utils.progress.threading.Event")
@mock.patch("deepfellow.infra.utils.progress.threading.Thread")
def test_heartbeat_stop_skips_join_when_thread_was_never_started(
    mock_thread: Mock,
    mock_event: Mock,
) -> None:
    mock_thread.return_value.is_alive.return_value = False
    heartbeat = _Heartbeat()

    heartbeat.stop()

    assert mock_event.return_value.set.call_count == 1
    assert mock_thread.return_value.join.call_count == 0


@mock.patch("deepfellow.infra.utils.progress._consume_sse")
@mock.patch("deepfellow.infra.utils.progress.echo.spinner")
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_closes_spinner_before_consuming_sse(
    mock_stream: Mock,
    mock_spinner: Mock,
    mock_consume_sse: Mock,
) -> None:
    events: list[str] = []
    mock_stream.return_value.__enter__.return_value = _stream_response()
    mock_spinner.return_value.__exit__.side_effect = lambda *_: events.append("spinner_exit")

    def consume_sse(_: Mock, __: str) -> dict[str, str]:
        events.append("consume_sse")
        return {"type": "finish", "status": "ok"}

    mock_consume_sse.side_effect = consume_sse

    result = install_with_progress(
        "http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}}, message="Installing model x..."
    )

    assert result == {"type": "finish", "status": "ok"}
    assert mock_spinner.call_args == mock.call("Installing model x...")
    assert events == ["spinner_exit", "consume_sse"]


@mock.patch("deepfellow.infra.utils.progress.echo.spinner")
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_shows_spinner_during_plain_json_fallback(
    mock_stream: Mock,
    mock_spinner: Mock,
) -> None:
    events: list[str] = []
    response = _stream_response(content_type="application/json", json_body={"status": "OK"})
    response.read.side_effect = lambda: events.append("read")
    mock_stream.return_value.__enter__.return_value = response
    mock_spinner.return_value.__enter__.side_effect = lambda: events.append("spinner_enter")
    mock_spinner.return_value.__exit__.side_effect = lambda *_: events.append("spinner_exit")

    result = install_with_progress("http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}})

    assert result == {"status": "OK"}
    assert mock_spinner.call_args == mock.call("Installing...")
    assert events == ["spinner_enter", "read", "spinner_exit"]


@mock.patch("deepfellow.infra.utils.progress.Progress")
@mock.patch("deepfellow.infra.utils.progress.is_interactive", return_value=True)
@mock.patch("deepfellow.infra.utils.progress.httpx.stream")
def test_install_with_progress_shows_message_row_for_whole_sse_stream(
    mock_stream: Mock,
    mock_is_interactive: Mock,
    mock_progress: Mock,
) -> None:
    progress = mock_progress.return_value.__enter__.return_value
    progress.add_task.return_value = "main-task"
    mock_stream.return_value.__enter__.return_value = _stream_response(
        lines=_sse_lines({"type": "finish", "status": "ok"})
    )

    install_with_progress(
        "http://infra:8086/admin/services/ollama", "test-key", data={"spec": {}}, message="Installing service ollama..."
    )

    assert progress.add_task.call_count == 1
    assert progress.add_task.call_args == mock.call("Installing service ollama...", total=None, header=True)
    assert progress.update.call_args_list == [mock.call("main-task", total=1.0, completed=1.0)]


def test_stage_only_column_renders_nothing_for_header_row() -> None:
    wrapped = Mock(name="column")
    task = Mock(fields={"header": True})
    column = _StageOnlyColumn(wrapped)

    result = column.render(task)

    assert str(result) == ""
    assert wrapped.render.call_count == 0


def test_stage_only_column_delegates_render_for_stage_row() -> None:
    wrapped = Mock(name="column")
    task = Mock(fields={})
    column = _StageOnlyColumn(wrapped)

    result = column.render(task)

    assert result is wrapped.render.return_value
    assert wrapped.render.call_args == mock.call(task)
