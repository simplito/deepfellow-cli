# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Streaming install helper: consume SSE progress from the Infra API and render it."""

import json
from collections.abc import Iterator
from typing import Any

import httpx
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn

from deepfellow.common.echo import echo, is_interactive

# Body key that switches the server to text/event-stream.
STREAM_BODY_KEY = "stream"

# How often to emit a plain-text progress line in non-interactive mode (0..1 step).
_NON_INTERACTIVE_STEP = 0.1


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
        # Mirror rest.post()'s handling of 4xx before raising for status.
        if response.status_code in (400, 401, 403):
            response.read()
            _raise_http_status(response)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            # Graceful degradation: server returned a single plain JSON response.
            response.read()
            return response.json()

        return _consume_sse(response)


def _raise_http_status(response: httpx.Response) -> None:
    """Raise HTTPStatusError so call_infra can extract the {"detail": ...} message."""
    raise httpx.HTTPStatusError(f"{response.status_code}", request=response.request, response=response)


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
    finish: dict[str, Any] = {"type": "finish", "status": "error"}
    columns = [
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
                    tasks[stage] = progress.add_task(stage.capitalize(), total=1.0)
                progress.update(tasks[stage], completed=value)
            elif etype == "finish":
                finish = event
                # Snap all bars to 100% on success.
                if event.get("status") == "ok":
                    for task_id in tasks.values():
                        progress.update(task_id, completed=1.0)
                break
    return finish


def _consume_non_interactive(response: httpx.Response) -> dict[str, Any]:
    finish: dict[str, Any] = {"type": "finish", "status": "error"}
    last_logged: dict[str, float] = {}
    for event in _iter_events(response):
        etype = event.get("type")
        if etype == "progress":
            stage = event.get("stage", "install")
            value = float(event.get("value") or 0.0)
            if value - last_logged.get(stage, -1.0) >= _NON_INTERACTIVE_STEP:
                last_logged[stage] = value
                echo.info(f"{stage}: {int(value * 100)}%")
        elif etype == "finish":
            finish = event
            break
    return finish
