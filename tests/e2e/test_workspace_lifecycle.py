# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Live check of workspace start/stop/restart/status/logs against a real, installed Workspace.

Skipped unless DF_E2E_WORKSPACE_DIRECTORY points at an installation made by `workspace install`.
The test stops and starts that Workspace, and leaves it running.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deepfellow.main import app

_DIRECTORY = os.environ.get("DF_E2E_WORKSPACE_DIRECTORY")

pytestmark = pytest.mark.skipif(not _DIRECTORY, reason="DF_E2E_WORKSPACE_DIRECTORY is not set")

runner = CliRunner()


@pytest.fixture
def directory() -> Iterator[str]:
    assert _DIRECTORY
    assert (Path(_DIRECTORY) / "compose.yaml").is_file()
    yield _DIRECTORY
    runner.invoke(app, ["--yes", "workspace", "start", "--directory", _DIRECTORY])


def _run(directory: str, *args: str) -> str:
    result = runner.invoke(app, ["--yes", "workspace", *args, "--directory", directory])
    assert result.exit_code == 0, result.output
    return result.output


def test_workspace_lifecycle_stop_status_start_restart_logs(directory: str) -> None:
    _run(directory, "stop")
    assert "not running" in _run(directory, "status")

    _run(directory, "start")
    assert "image:" in _run(directory, "status")

    _run(directory, "restart")
    assert "image:" in _run(directory, "status")

    assert "Showing DeepFellow Workspace logs" in _run(directory, "logs", "-n", "3")
