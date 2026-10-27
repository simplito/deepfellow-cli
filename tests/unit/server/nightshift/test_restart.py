# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock

import pytest
import typer

from deepfellow.server.nightshift.restart import restart


@mock.patch("deepfellow.server.nightshift.restart.restart_nightshift")
@mock.patch("deepfellow.server.nightshift.restart.service_running_or_exit", return_value=True)
@mock.patch("deepfellow.server.nightshift.restart.assert_nightshift_installed")
@mock.patch("deepfellow.server.nightshift.restart.assert_docker")
@mock.patch("deepfellow.server.nightshift.restart.check_server_directory")
def test_restart_restarts_only_nightshift(
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_assert_installed: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_restart_nightshift: mock.MagicMock,
    directory: Path,
) -> None:
    restart(directory=directory)

    assert mock_check_server_directory.call_count == 1
    assert mock_check_server_directory.call_args == mock.call(directory)
    assert mock_assert_docker.call_count == 1
    assert mock_restart_nightshift.call_count == 1
    assert mock_restart_nightshift.call_args == mock.call(directory)
    assert mock_is_service_running.call_args == mock.call("server", directory)
    assert mock_assert_installed.call_args == mock.call(directory)


@mock.patch("deepfellow.server.nightshift.restart.echo")
@mock.patch("deepfellow.server.nightshift.restart.restart_nightshift")
@mock.patch("deepfellow.server.nightshift.restart.service_running_or_exit", return_value=False)
@mock.patch("deepfellow.server.nightshift.restart.assert_nightshift_installed")
@mock.patch("deepfellow.server.nightshift.restart.assert_docker")
@mock.patch("deepfellow.server.nightshift.restart.check_server_directory")
def test_restart_fails_with_a_warning_when_the_server_is_not_running(
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_assert_installed: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_restart_nightshift: mock.MagicMock,
    mock_echo: mock.MagicMock,
    directory: Path,
) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        restart(directory=directory)

    assert exc_info.value.exit_code == 1
    assert mock_echo.warning.call_count == 1
    assert mock_restart_nightshift.call_count == 0


@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.nightshift.restart.restart_nightshift")
@mock.patch("deepfellow.server.nightshift.restart.assert_docker")
@mock.patch("deepfellow.server.nightshift.restart.check_server_directory")
def test_restart_fails_with_a_hint_when_the_install_has_no_nightshift_service(
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_restart_nightshift: mock.MagicMock,
    mock_echo: mock.MagicMock,
    directory: Path,
) -> None:
    """An install from before Nightshift existed has no `nightshift` service in compose.yaml."""
    with pytest.raises(typer.Exit) as exc_info:
        restart(directory=directory)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    assert mock_restart_nightshift.call_count == 0
