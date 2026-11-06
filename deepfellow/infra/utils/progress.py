# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Streaming install helper: consume SSE progress from the Infra API and render it.

Stages that report no intermediate progress get an activity indicator instead of a bar
frozen at 0%: a spinner with a pulsing bar in interactive mode, a periodic ``still working…``
line in non-interactive mode. The Infra API emits only ``value=0`` and ``value=1`` for the
``install`` stage, with the Docker pull/healthcheck wait in between, so without this the
CLI looks hung for minutes.

A progress event may name the Docker image being pulled in ``data.image``. The stage is then
labelled ``Pulling image <name>`` and shown as a regular bar from 0%. The label never comes from
the stage name alone: ``download`` is also the stage of model downloads.

A download event may also carry its byte counts in ``data.completed`` and ``data.total``. The row
then shows the downloaded and total size, the transfer speed and the time remaining.
"""

import json
import threading
from collections.abc import Iterator
from contextlib import ExitStack
from datetime import timedelta
from typing import Any

import httpx
from rich import filesize
from rich.console import RenderableType
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text

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
# Task field marking the install-message row, which shows no bar or percentage of its own.
_HEADER_FIELD = "header"
# Task field holding a stage's ``(completed, total)`` bytes, once its events report them. Set as
# ``progress.update(task_id, bytes=...)``: rich types the ``**fields`` of ``update`` too loosely to unpack a dict.
_BYTES_FIELD = "bytes"
# Keys in a progress event's ``data``: the image being pulled, and the bytes downloaded so far and in total.
# Infra versions that send none of them get the stage name as label and a bar without sizes.
_IMAGE_DATA_KEY = "image"
_COMPLETED_DATA_KEY = "completed"
_TOTAL_DATA_KEY = "total"


def install_with_progress(
    url: str,
    token: str,
    data: dict[str, Any],
    timeout: float = 60 * 60 * 24,
    message: str = "Installing...",
    method: str = "POST",
) -> dict[str, Any]:
    """Send a request with stream=true and render progress; fall back to plain JSON if unsupported.

    Args:
        url: Full endpoint URL.
        token: Bearer token (Infra admin API key).
        data: Request body; ``{"stream": true}`` is injected automatically.
        timeout: Read timeout for the long-running download.
        message: Install message shown with a spinner for the whole install.
        method: HTTP method of the endpoint (``POST`` or ``PUT``).

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
    echo.debug(f"{method} (stream) {url} data={body}")

    with ExitStack() as stack:
        # Spinner must close before _consume_sse starts Progress — rich allows one live display at a time.
        with echo.spinner(message):
            response = stack.enter_context(httpx.stream(method, url, headers=headers, json=body, timeout=timeout))
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

        return _consume_sse(response, message)


def _consume_sse(response: httpx.Response, message: str) -> dict[str, Any]:
    """Read SSE chunks to the terminal 'finish' event, rendering progress."""
    if is_interactive():
        return _consume_interactive(response, message)
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


def _event_image(event: dict[str, Any]) -> str | None:
    """Return the image named in a progress event's ``data``, or ``None`` if it names none."""
    data = event.get("data")
    image = data.get(_IMAGE_DATA_KEY) if isinstance(data, dict) else None
    return image if isinstance(image, str) and image else None


def _event_bytes(event: dict[str, Any]) -> tuple[int, int] | None:
    """Return the ``(completed, total)`` bytes of a progress event, or ``None`` if its total is unknown."""
    data = event.get("data")
    if not isinstance(data, dict):
        return None
    completed, total = data.get(_COMPLETED_DATA_KEY), data.get(_TOTAL_DATA_KEY)
    if isinstance(completed, int) and isinstance(total, int) and total > 0:
        return completed, total
    return None


def _stage_bytes(
    event: dict[str, Any], stage: str, value: float, byte_totals: dict[str, int]
) -> tuple[int, int] | None:
    """Return a stage's ``(completed, total)`` bytes after `event`, recording its total in `byte_totals`.

    Infra closes a download with a bare ``value=1``, so an event without bytes is scaled from the
    stage's last known total.
    """
    if (sizes := _event_bytes(event)) is not None:
        byte_totals[stage] = sizes[1]
        return sizes
    if stage in byte_totals:
        return int(value * byte_totals[stage]), byte_totals[stage]
    return None


def _stage_label(stage: str, image: str | None) -> str:
    """Return the row label of a stage: the image being pulled, or the capitalized stage name."""
    return f"Pulling image {image}" if image else stage.capitalize()


class _StageOnlyColumn(ProgressColumn):
    """Render the wrapped column for stage rows only, leaving the install-message row blank."""

    def __init__(self, column: ProgressColumn) -> None:
        """Wrap a column so it is skipped on the header row.

        Args:
            column: Column rendered for every row except the header.
        """
        super().__init__()
        self._column = column

    def render(self, task: Task) -> RenderableType:
        """Render the wrapped column, or nothing for the header row."""
        if task.fields.get(_HEADER_FIELD):
            return Text()
        return self._column.render(task)


class _BytesColumn(ProgressColumn):
    """Render a downloading stage's size, transfer speed and time remaining; nothing for other rows."""

    def render(self, task: Task) -> RenderableType:
        """Render e.g. ``1.2/3.4 GB 25.0 MB/s 0:01:20``, leaving out speed and time until they are known."""
        sizes: tuple[int, int] | None = task.fields.get(_BYTES_FIELD)
        if sizes is None:
            return Text()
        completed, total = sizes
        unit, suffix = filesize.pick_unit_and_suffix(total, ["bytes", "kB", "MB", "GB", "TB"], 1000)
        parts = [f"{completed / unit:.1f}/{total / unit:.1f} {suffix}"]
        # Task progress runs 0..1, so its speed is a fraction of the total per second. Infra derives the
        # event's value and data.completed/data.total from one counter (value == completed / total, with
        # total covering the whole download, not one layer), so scaling by the total gives bytes per second.
        if task.speed and not task.finished:
            parts.append(f"{filesize.decimal(int(task.speed * total))}/s")
        if task.time_remaining is not None and not task.finished:
            parts.append(str(timedelta(seconds=int(task.time_remaining))))
        return Text(" ".join(parts), style="progress.download")


def _consume_interactive(response: httpx.Response, message: str) -> dict[str, Any]:
    """Render progress bars; a stage with no intermediate values pulses with a spinner."""
    finish: dict[str, Any] = {"type": "finish", "status": "error"}
    columns = [
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        _StageOnlyColumn(BarColumn()),
        _StageOnlyColumn(TaskProgressColumn()),
        _BytesColumn(),
        TimeElapsedColumn(),
    ]
    with Progress(*columns, console=echo) as progress:
        # Headers arrive as soon as the server starts streaming, often long before the first progress
        # event, so keep a spinner row with the install message visible for the whole stream. It carries no bar:
        # the stage rows below it show the actual progress.
        main_task = progress.add_task(message, total=None, **{_HEADER_FIELD: True})
        tasks: dict[str, Any] = {}  # stage -> task_id
        pulls: set[str] = set()  # stages that named the image they pull
        byte_totals: dict[str, int] = {}  # stage -> total bytes, once an event reported them
        for event in _iter_events(response):
            etype = event.get("type")
            if etype == "progress":
                stage = event.get("stage", "install")
                value = float(event.get("value") or 0.0)
                image = _event_image(event)
                if stage not in tasks:
                    # total=None makes the bar pulse, so a stage reporting only 0 then 1
                    # reads as working rather than frozen at 0%.
                    tasks[stage] = progress.add_task(f"{_stage_label(stage, image)}…", total=None)
                elif image and stage not in pulls:
                    progress.update(tasks[stage], description=f"{_stage_label(stage, image)}…")
                if image:
                    pulls.add(stage)
                # Progress.update treats total=None as "leave unchanged", so the task stays
                # indeterminate until the first real value promotes it to a normal bar. A pull
                # reports real progress from the start, so its bar is determinate from 0%.
                determinate = value > 0 or stage in pulls
                progress.update(tasks[stage], completed=value, total=1.0 if determinate else None)
                if (sizes := _stage_bytes(event, stage, value, byte_totals)) is not None:
                    progress.update(tasks[stage], bytes=sizes)
            elif etype == "finish":
                finish = event
                if event.get("status") == "ok":
                    _complete_tasks(progress, [main_task, *tasks.values()])
                    for stage, total in byte_totals.items():
                        progress.update(tasks[stage], bytes=(total, total))
                break
    return finish


def _complete_tasks(progress: Progress, task_ids: list[Any]) -> None:
    """Snap bars to 100% - including any still-indeterminate one, which needs its total set to show completion."""
    for task_id in task_ids:
        progress.update(task_id, total=1.0, completed=1.0)


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
    labels: dict[str, str] = {}  # stage -> label, once an event named the image it pulls
    byte_totals: dict[str, int] = {}  # stage -> total bytes, once an event reported them
    heartbeat = _Heartbeat()
    heartbeat.start()
    try:
        for event in _iter_events(response):
            etype = event.get("type")
            if etype == "progress":
                stage = event.get("stage", "install")
                value = float(event.get("value") or 0.0)
                if image := _event_image(event):
                    labels[stage] = _stage_label(stage, image)
                label = labels.get(stage, stage)
                # Called for every event, logged or not, so the final bare value=1 still gets a total.
                sizes = _stage_bytes(event, stage, value, byte_totals)
                if value - last_logged.get(stage, -1.0) >= _NON_INTERACTIVE_STEP:
                    last_logged[stage] = value
                    size = f" ({filesize.decimal(sizes[0])} / {filesize.decimal(sizes[1])})" if sizes else ""
                    echo.info(f"{label}: {int(value * 100)}%{size}")
                # Any event proves the install is alive, so a stage that keeps ticking
                # (download) never reaches a heartbeat line.
                heartbeat.notify(label if value < 1.0 else None)
            elif etype == "finish":
                finish = event
                break
    finally:
        # The stream can also end by exception (read error, interrupt) before 'finish'.
        heartbeat.stop()
    return finish
