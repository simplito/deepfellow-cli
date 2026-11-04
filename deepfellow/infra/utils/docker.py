# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Util to perform infra-specific docker operations."""

import re
import time
from pathlib import Path
from typing import NoReturn

from deepfellow.common.defaults import INFRA_PULL_WAIT_TIMEOUT_SECONDS
from deepfellow.common.docker import (
    DockerError,
    ensure_network,
    get_docker_network,
    is_service_running_or_raise,
    service_health,
)
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.system import run

INFRA_SERVICE = "infra"
# Infra logs this line before it pulls an image a service needs (deepfellow-infra `server/docker.py`).
_PULL_LOG_PATTERN = re.compile(r"Image '([^']+)' not found locally")
# How often to check Infra's health while it pulls images at startup.
_PULL_WAIT_POLL_SECONDS = 5.0
# How often to report that Infra is still pulling, so a long wait never looks hung (e.g. in a CI job log).
_PULL_WAIT_REPORT_SECONDS = 60.0


def start_infra(directory: Path) -> None:
    """Ensure network and start infra.

    Infra pulls the images of installed services that are missing locally before it serves /health,
    so `docker compose up --wait` can report it unhealthy while it is only pulling. In that case wait
    for the pulls to finish instead of failing.
    """
    ensure_network(get_docker_network(directory))
    try:
        run(["docker", "compose", "up", "-d", "--wait", "--remove-orphans"], cwd=directory, raises=DockerError)
    except DockerError as exc:
        _wait_for_startup_pulls(directory, exc)


def stop_infra(directory: Path) -> None:
    """Stop infra."""
    run(["docker", "compose", "stop", INFRA_SERVICE], cwd=directory)


def _container_started_at(directory: Path) -> str | None:
    """Return when the current Infra container started (RFC 3339), or None if it can't be read."""
    try:
        container_id = run(
            ["docker", "compose", "ps", "-q", INFRA_SERVICE], cwd=directory, capture_output=True, raises=DockerError
        )
        container_id = (container_id or "").strip()
        if not container_id:
            return None
        started_at = run(
            ["docker", "inspect", "-f", "{{.State.StartedAt}}", container_id], capture_output=True, raises=DockerError
        )
    except DockerError as exc:
        echo.debug(exc)
        return None
    return (started_at or "").strip() or None


def _startup_pull_images(directory: Path) -> list[str]:
    """Return the images the current Infra container started pulling, in log order, without duplicates.

    Only logs since the container's last start count: a restarted container keeps its older logs, and
    a pull from an earlier run says nothing about why this start failed.
    """
    started_at = _container_started_at(directory)
    if started_at is None:
        return []
    try:
        logs = run(
            ["docker", "compose", "logs", "--no-log-prefix", "--since", started_at, INFRA_SERVICE],
            cwd=directory,
            capture_output=True,
            raises=DockerError,
        )
    except DockerError as exc:
        echo.debug(exc)
        return []
    return list(dict.fromkeys(_PULL_LOG_PATTERN.findall(logs or "")))


def _report_start_failure(exc: DockerError) -> NoReturn:
    """Report a failed infra start. Must be called from the `except` block handling `exc`."""
    if not exc.args or exc.args[0] in (None, ""):
        # docker compose up's own output streams straight to the terminal (never captured), so
        # a plain DockerError from it carries no stderr of its own to show here.
        echo.error("Failed to start DeepFellow Infra. See the Docker output above for details.")
    else:
        echo.error(f"Failed to start DeepFellow Infra: {exc}")
    reraise_if_debug(exc)


def _infra_running(directory: Path) -> bool | None:
    """Tell whether Infra is running; `None` when `docker compose ps` itself fails (unknown)."""
    try:
        return is_service_running_or_raise(INFRA_SERVICE, directory)
    except DockerError as exc:
        echo.debug(exc)
        return None


def _wait_for_startup_pulls(directory: Path, exc: DockerError) -> None:
    """Wait for Infra to become healthy if it is still pulling service images; otherwise report `exc`.

    Must be called from the `except` block handling `exc`. Returns once Infra is healthy;
    exits (or re-raises in debug mode) when it isn't pulling, is confirmed stopped, or isn't healthy within
    `INFRA_PULL_WAIT_TIMEOUT_SECONDS`.
    Reports progress every `_PULL_WAIT_REPORT_SECONDS` so the wait never looks hung.
    """
    images = _startup_pull_images(directory)
    if not images or not _infra_running(directory):
        _report_start_failure(exc)

    echo.warning(
        f"DeepFellow Infra is still pulling service images ({', '.join(images)}) - this can take several "
        "minutes. Waiting..."
    )
    start = time.monotonic()
    deadline = start + INFRA_PULL_WAIT_TIMEOUT_SECONDS
    next_report = start + _PULL_WAIT_REPORT_SECONDS
    with echo.spinner("Waiting for DeepFellow Infra to pull service images..."):
        while service_health(directory, INFRA_SERVICE) != "healthy":
            if _infra_running(directory) is False:
                echo.error("DeepFellow Infra stopped while pulling service images. Check `deepfellow infra logs`.")
                reraise_if_debug(exc)
            now = time.monotonic()
            if now >= deadline:
                minutes = INFRA_PULL_WAIT_TIMEOUT_SECONDS // 60
                echo.error(
                    f"DeepFellow Infra isn't healthy after {minutes} minutes of pulling service images. "
                    "Check `deepfellow infra logs`."
                )
                reraise_if_debug(exc)
            if now >= next_report:
                echo.info(f"Still waiting for DeepFellow Infra to pull service images... ({int(now - start)}s)")
                next_report += _PULL_WAIT_REPORT_SECONDS
            time.sleep(_PULL_WAIT_POLL_SECONDS)
    echo.success("DeepFellow Infra is up.")
