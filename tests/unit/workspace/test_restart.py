# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.workspace.restart import restart


@mock.patch("deepfellow.workspace.restart.workspace_url", return_value="http://localhost:3000")
@mock.patch("deepfellow.workspace.restart.echo")
@mock.patch("deepfellow.workspace.restart.confirm_server_running")
@mock.patch("deepfellow.workspace.restart.start_workspace")
@mock.patch("deepfellow.workspace.restart.stop_workspace")
@mock.patch("deepfellow.workspace.restart.assert_docker")
def test_restart_confirms_server_then_stops_then_starts(
    mock_assert_docker: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_confirm: Mock,
    mock_echo: Mock,
    mock_url: Mock,
    tmp_path: Path,
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")
    calls = Mock()
    calls.attach_mock(mock_confirm, "confirm")
    calls.attach_mock(mock_stop, "stop")
    calls.attach_mock(mock_start, "start")

    restart(directory=tmp_path)

    assert calls.mock_calls == [mock.call.confirm(tmp_path), mock.call.stop(tmp_path), mock.call.start(tmp_path)]
    assert mock_echo.info.call_args == mock.call("DeepFellow Workspace restarted on http://localhost:3000")


@mock.patch("deepfellow.workspace.restart.confirm_server_running", side_effect=typer.Exit(1))
@mock.patch("deepfellow.workspace.restart.start_workspace")
@mock.patch("deepfellow.workspace.restart.stop_workspace")
@mock.patch("deepfellow.workspace.restart.assert_docker")
def test_restart_server_down_declined_keeps_workspace_running(
    mock_assert_docker: Mock, mock_stop: Mock, mock_start: Mock, mock_confirm: Mock, tmp_path: Path
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    with pytest.raises(typer.Exit):
        restart(directory=tmp_path)

    assert mock_stop.call_count == 0
    assert mock_start.call_count == 0


@mock.patch("deepfellow.workspace.restart.start_workspace")
@mock.patch("deepfellow.workspace.restart.stop_workspace")
@mock.patch("deepfellow.workspace.restart.assert_docker")
def test_restart_without_installation_exits(
    mock_assert_docker: Mock, mock_stop: Mock, mock_start: Mock, tmp_path: Path
) -> None:
    with pytest.raises(typer.Exit):
        restart(directory=tmp_path)

    assert mock_stop.call_count == 0
    assert mock_start.call_count == 0
