# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.workspace.stop import stop


@mock.patch("deepfellow.workspace.stop.echo")
@mock.patch("deepfellow.workspace.stop.stop_workspace")
@mock.patch("deepfellow.workspace.stop.assert_docker")
def test_stop_stops_workspace(mock_assert_docker: Mock, mock_stop: Mock, mock_echo: Mock, tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    stop(directory=tmp_path)

    assert mock_assert_docker.call_count == 1
    assert mock_stop.call_args == mock.call(tmp_path)
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.workspace.stop.stop_workspace")
@mock.patch("deepfellow.workspace.stop.assert_docker")
def test_stop_without_installation_exits(mock_assert_docker: Mock, mock_stop: Mock, tmp_path: Path) -> None:
    with pytest.raises(typer.Exit):
        stop(directory=tmp_path)

    assert mock_stop.call_count == 0
