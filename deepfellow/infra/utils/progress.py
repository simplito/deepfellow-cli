# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Streaming install helper: consume SSE progress from the Infra API and render it.

Stages that report no intermediate progress get an activity indicator instead of a bar
frozen at 0%: a spinner with a pulsing bar in interactive mode, a periodic ``still working…``
line in non-interactive mode. The Infra API emits only ``value=0`` and ``value=1`` for the
``install`` stage, with the Docker pull/healthcheck wait in between, so without this the
CLI looks hung for minutes.
"""

import json
import threading
from collections.abc import Iterator
from typing import Any

import httpx
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from deepfellow.common.echo import echo, is_interactive

# Body key that switches the server to text/event-stream.
STREAM_BODY_KEY = "stream"

# How often to emit a plain-text progress line in non-interactive mode (0..1 step).
_NON_INTERACTIVE_STEP = 0.1
# Seconds of silence before a "still working" line appears. The stall this guards against (a
# Docker pull) lasts minutes, so the threshold sits well above an ordinary gap between events.
_HEARTBEAT_INTERVAL = 15.0
# How often the worker wakes to measure the silence; also its stop latency.
_HEARTBEAT_POLL = 1.0


def install_with_progress(
    url: str,
    token: str,
    data: dict[str, Any],
    timeout: float = 60 * 60 * 24,
) -> dict[str, Any]:
    """POST with stream=true and render progress; fall back to plain JSON if unsupported.

    Args:
        url: Full endpoint URL.
        token: Bearer token (Infra admin API key).
        data: Request body; ``{"stream": true}`` is injected automatically.
        timeout: Read timeout for the long-running download.

    Returns:
        The terminal payload as a dict. For an SSE response this is the
        ``{"type": "finish", "status": "ok"|"error", ...}`` chunk. For a
        non-streaming server it is the plain JSON body unchanged.

    Raises:
        httpx.HTTPError: transport / status errors, so the caller can route
            them through ``call_infra`` exactly like the blocking ``post``.
    """
    body = data | {STREAM_BODY_KEY: True}
    headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
    echo.debug(f"POST (stream) {url} data={body}")

    with httpx.stream("POST", url, headers=headers, json=body, timeout=timeout) as response:
        # Any error status must be read here, inside the stream context - `call_infra` reads
        # `exc.response.json()`/`.text` from the raised error to build its message, and once this
        # `with` block exits the unread body is gone, raising `httpx.ResponseNotRead` instead.
        if response.is_error:
            response.read()
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            # Graceful degradation: server returned a single plain JSON response.
            response.read()
            return response.json()

        return _consume_sse(response)


def _consume_sse(response: httpx.Response) -> dict[str, Any]:
    """Read SSE chunks to the terminal 'finish' event, rendering progress."""
    if is_interactive():
        return _consume_interactive(response)
    return _consume_non_interactive(response)


def _iter_events(response: httpx.Response) -> Iterator[dict[str, Any]]:
    """Yield parsed JSON objects from SSE (or NDJSON) lines."""
    for line in response.iter_lines():
        line = line.strip()
        if not line:
            continue
        # Tolerate both "data: {...}" (SSE) and bare "{...}" (NDJSON).
        if line.startswith("data:"):
            line = line[len("data:") :].strip()
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            echo.debug(f"Skipping non-JSON stream line: {line!r}")


def _consume_interactive(response: httpx.Response) -> dict[str, Any]:
    """Render progress bars; a stage with no intermediate values pulses with a spinner."""
    finish: dict[str, Any] = {"type": "finish", "status": "error"}
    columns = [
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
    ]
    with Progress(*columns, console=echo) as progress:
        tasks: dict[str, Any] = {}  # stage -> task_id
        for event in _iter_events(response):
            etype = event.get("type")
            if etype == "progress":
                stage = event.get("stage", "install")
                value = float(event.get("value") or 0.0)
                if stage not in tasks:
                    # total=None makes the bar pulse, so a stage reporting only 0 then 1
                    # reads as working rather than frozen at 0%.
                    tasks[stage] = progress.add_task(f"{stage.capitalize()}…", total=None)
                # Progress.update treats total=None as "leave unchanged", so the task stays
                # indeterminate until the first real value promotes it to a normal bar.
                progress.update(tasks[stage], completed=value, total=1.0 if value > 0 else None)
            elif etype == "finish":
                finish = event
                # Snap all bars to 100% on success — including any still-indeterminate one,
                # which needs its total set before it can show completion.
                if event.get("status") == "ok":
                    for task_id in tasks.values():
                        progress.update(task_id, total=1.0, completed=1.0)
                break
    return finish


class _Heartbeat:
    """Print a 'still working' line whenever the stream goes quiet for too long.

    A single instance runs for the whole stream. Every progress event calls ``notify``,
    which restarts the silence timer, so a stage that keeps ticking never produces a
    line — only a gap longer than ``interval`` does.
    """

    def __init__(self, interval: float = _HEARTBEAT_INTERVAL, poll: float = _HEARTBEAT_POLL) -> None:
        """Initialize the heartbeat without starting it.

        Args:
            interval: Seconds of silence before a line appears, and between lines.
            poll: How often the worker wakes to measure the silence.
        """
        self.interval = interval
        self.poll = poll
        self._stage: str | None = None
        self._silent = 0.0
        self._next = interval
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="heartbeat", daemon=True)

    def start(self) -> None:
        """Start the worker; it stays quiet until a stage is notified and then stalls."""
        self._thread.start()

    def notify(self, stage: str | None) -> None:
        """Record that the stream is alive and restart the silence timer.

        Args:
            stage: Stage to name in the next line, or ``None`` when nothing is in flight
                (the stage just reached 100%), which keeps the worker silent until the
                next stage reports in.
        """
        with self._lock:
            self._stage = stage
            self._silent = 0.0
            self._next = self.interval

    def stop(self) -> None:
        """Stop printing and wait for the worker to finish.

        The flag is set under the lock the worker holds while it prints, so once this
        returns no further line can appear.
        """
        with self._lock:
            self._stop.set()
        if self._thread.is_alive():
            self._thread.join()

    def _run(self) -> None:
        """Print one line per ``interval`` of uninterrupted silence until stopped.

        Elapsed time is accumulated from the poll interval rather than read from a
        clock, so the output is deterministic and testable.
        """
        while not self._stop.wait(self.poll):
            with self._lock:
                if self._stop.is_set():
                    return
                self._silent += self.poll
                if self._stage is None or self._silent < self._next:
                    continue
                self._next += self.interval
                echo.info(f"{self._stage}: still working… ({int(self._silent)}s)")


def _consume_non_interactive(response: httpx.Response) -> dict[str, Any]:
    """Log progress as plain lines, with a heartbeat while the current stage stays silent."""
    finish: dict[str, Any] = {"type": "finish", "status": "error"}
    last_logged: dict[str, float] = {}
    heartbeat = _Heartbeat()
    heartbeat.start()
    try:
        for event in _iter_events(response):
            etype = event.get("type")
            if etype == "progress":
                stage = event.get("stage", "install")
                value = float(event.get("value") or 0.0)
                if value - last_logged.get(stage, -1.0) >= _NON_INTERACTIVE_STEP:
                    last_logged[stage] = value
                    echo.info(f"{stage}: {int(value * 100)}%")
                # Any event proves the install is alive, so a stage that keeps ticking
                # (download) never reaches a heartbeat line.
                heartbeat.notify(stage if value < 1.0 else None)
            elif etype == "finish":
                finish = event
                break
    finally:
        # The stream can also end by exception (read error, interrupt) before 'finish'.
        heartbeat.stop()
    return finish
