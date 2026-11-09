# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.workspace.status import status


@mock.patch("deepfellow.workspace.status.is_service_running", return_value=True)
@mock.patch("deepfellow.workspace.status.print_docker_status")
@mock.patch("deepfellow.workspace.status.assert_docker")
def test_status_prints_workspace_status(
    mock_assert_docker: Mock, mock_print: Mock, mock_running: Mock, tmp_path: Path
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    status(directory=tmp_path)

    assert mock_print.call_args == mock.call(tmp_path, "workspace")


@mock.patch("deepfellow.workspace.status.print_docker_status")
@mock.patch("deepfellow.workspace.status.assert_docker")
def test_status_without_installation_exits(mock_assert_docker: Mock, mock_print: Mock, tmp_path: Path) -> None:
    with pytest.raises(typer.Exit):
        status(directory=tmp_path)

    assert mock_print.call_count == 0


@mock.patch("deepfellow.workspace.status.echo")
@mock.patch("deepfellow.workspace.status.is_service_running", return_value=False)
@mock.patch("deepfellow.workspace.status.print_docker_status")
@mock.patch("deepfellow.workspace.status.assert_docker")
def test_status_not_running_reports_it_without_docker_stats(
    mock_assert_docker: Mock, mock_print: Mock, mock_running: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    status(directory=tmp_path)

    assert mock_print.call_count == 0
    assert "not running" in mock_echo.info.call_args.args[0]
