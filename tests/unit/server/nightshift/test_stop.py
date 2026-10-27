# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock

import pytest
import typer

from deepfellow.server.nightshift.stop import stop


@mock.patch("deepfellow.server.nightshift.stop.stop_nightshift")
@mock.patch("deepfellow.server.nightshift.stop.assert_nightshift_installed")
@mock.patch("deepfellow.server.nightshift.stop.assert_docker")
@mock.patch("deepfellow.server.nightshift.stop.check_server_directory")
def test_stop_stops_only_nightshift(
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_assert_installed: mock.MagicMock,
    mock_stop_nightshift: mock.MagicMock,
    directory: Path,
) -> None:
    stop(directory=directory)

    assert mock_check_server_directory.call_count == 1
    assert mock_check_server_directory.call_args == mock.call(directory)
    assert mock_assert_docker.call_count == 1
    assert mock_stop_nightshift.call_count == 1
    assert mock_stop_nightshift.call_args == mock.call(directory)
    assert mock_assert_installed.call_args == mock.call(directory)


@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.nightshift.stop.stop_nightshift")
@mock.patch("deepfellow.server.nightshift.stop.assert_docker")
@mock.patch("deepfellow.server.nightshift.stop.check_server_directory")
def test_stop_fails_with_a_hint_when_the_install_has_no_nightshift_service(
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_stop_nightshift: mock.MagicMock,
    mock_echo: mock.MagicMock,
    directory: Path,
) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        stop(directory=directory)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    assert mock_stop_nightshift.call_count == 0
