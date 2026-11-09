# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.workspace.start import start


@mock.patch("deepfellow.workspace.start.workspace_url", return_value="http://localhost:3000")
@mock.patch("deepfellow.workspace.start.echo")
@mock.patch("deepfellow.workspace.start.confirm_server_running")
@mock.patch("deepfellow.workspace.start.start_workspace")
@mock.patch("deepfellow.workspace.start.assert_docker")
def test_start_starts_workspace(
    mock_assert_docker: Mock, mock_start: Mock, mock_confirm: Mock, mock_echo: Mock, mock_url: Mock, tmp_path: Path
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    start(directory=tmp_path)

    assert mock_assert_docker.call_count == 1
    assert mock_confirm.call_args == mock.call(tmp_path)
    assert mock_start.call_args == mock.call(tmp_path)
    assert mock_echo.info.call_args == mock.call("DeepFellow Workspace started on http://localhost:3000")


@mock.patch("deepfellow.workspace.start.start_workspace")
@mock.patch("deepfellow.workspace.start.assert_docker")
def test_start_without_installation_exits(mock_assert_docker: Mock, mock_start: Mock, tmp_path: Path) -> None:
    with pytest.raises(typer.Exit):
        start(directory=tmp_path)

    assert mock_start.call_count == 0


@mock.patch("deepfellow.workspace.start.confirm_server_running", side_effect=typer.Exit(1))
@mock.patch("deepfellow.workspace.start.start_workspace")
@mock.patch("deepfellow.workspace.start.assert_docker")
def test_start_server_down_declined_does_not_start(
    mock_assert_docker: Mock, mock_start: Mock, mock_confirm: Mock, tmp_path: Path
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    with pytest.raises(typer.Exit):
        start(directory=tmp_path)

    assert mock_start.call_count == 0
