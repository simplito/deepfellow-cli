# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.workspace.logs import logs


@mock.patch("deepfellow.workspace.logs.echo")
@mock.patch("deepfellow.workspace.logs.run")
@mock.patch("deepfellow.workspace.logs.assert_docker")
def test_logs_shows_tail_of_app_logs(mock_assert_docker: Mock, mock_run: Mock, mock_echo: Mock, tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    logs(directory=tmp_path, follow=False, tail=20)

    assert mock_run.call_args == mock.call(["docker", "compose", "logs", "workspace", "--tail", "20"], cwd=tmp_path)


@mock.patch("deepfellow.workspace.logs.echo")
@mock.patch("deepfellow.workspace.logs.run")
@mock.patch("deepfellow.workspace.logs.assert_docker")
def test_logs_follow_adds_flag(mock_assert_docker: Mock, mock_run: Mock, mock_echo: Mock, tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    logs(directory=tmp_path, follow=True, tail=None)

    assert mock_run.call_args == mock.call(["docker", "compose", "logs", "workspace", "-f"], cwd=tmp_path)


@mock.patch("deepfellow.workspace.logs.run")
@mock.patch("deepfellow.workspace.logs.assert_docker")
def test_logs_without_installation_exits(mock_assert_docker: Mock, mock_run: Mock, tmp_path: Path) -> None:
    with pytest.raises(typer.Exit):
        logs(directory=tmp_path, follow=False, tail=20)

    assert mock_run.call_count == 0
