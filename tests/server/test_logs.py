# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock

import pytest
import typer

from deepfellow.server.logs import logs


@mock.patch("deepfellow.server.logs.run")
@mock.patch("deepfellow.server.logs.echo.info")
@mock.patch("deepfellow.server.logs.assert_docker")
def test_logs_runs_docker_compose_logs_with_default_tail(
    mock_assert_docker: mock.MagicMock,
    mock_info: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
) -> None:
    logs(directory=directory, follow=False, tail=20, nightshift=False)

    assert mock_assert_docker.call_count == 1
    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call("Showing DeepFellow Server logs")
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "logs", "server", "--tail", "20"], cwd=directory)


@mock.patch("deepfellow.server.logs.run")
@mock.patch("deepfellow.server.logs.echo.info")
@mock.patch("deepfellow.server.logs.assert_docker")
def test_logs_appends_follow_flag_when_follow_is_true(
    mock_assert_docker: mock.MagicMock,
    mock_info: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
) -> None:
    logs(directory=directory, follow=True, tail=20, nightshift=False)

    assert mock_assert_docker.call_count == 1
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "logs", "server", "-f", "--tail", "20"], cwd=directory)


@mock.patch("deepfellow.server.logs.run")
@mock.patch("deepfellow.server.logs.echo.info")
@mock.patch("deepfellow.server.logs.assert_docker")
def test_logs_omits_follow_flag_when_follow_is_false(
    mock_assert_docker: mock.MagicMock,
    mock_info: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
) -> None:
    logs(directory=directory, follow=False, tail=50, nightshift=False)

    assert mock_assert_docker.call_count == 1
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "logs", "server", "--tail", "50"], cwd=directory)


@mock.patch("deepfellow.server.logs.run")
@mock.patch("deepfellow.server.logs.echo.info")
@mock.patch("deepfellow.server.logs.assert_docker")
def test_logs_omits_tail_flag_when_tail_is_none(
    mock_assert_docker: mock.MagicMock,
    mock_info: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
) -> None:
    logs(directory=directory, follow=False, tail=None, nightshift=False)

    assert mock_assert_docker.call_count == 1
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "logs", "server"], cwd=directory)


@mock.patch("deepfellow.server.logs.run")
@mock.patch("deepfellow.server.logs.echo.info")
@mock.patch("deepfellow.server.logs.assert_nightshift_installed")
@mock.patch("deepfellow.server.logs.assert_docker")
def test_logs_shows_nightshift_logs_when_nightshift_flag_set(
    mock_assert_docker: mock.MagicMock,
    mock_assert_installed: mock.MagicMock,
    mock_info: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
) -> None:
    logs(directory=directory, follow=False, tail=20, nightshift=True)

    assert mock_assert_installed.call_args == mock.call(directory)
    assert mock_info.call_args == mock.call("Showing DeepFellow Nightshift worker logs")
    assert mock_run.call_args == mock.call(["docker", "compose", "logs", "nightshift", "--tail", "20"], cwd=directory)


@mock.patch("deepfellow.server.logs.run")
@mock.patch("deepfellow.server.logs.assert_nightshift_installed", side_effect=typer.Exit(1))
@mock.patch("deepfellow.server.logs.assert_docker")
def test_logs_nightshift_flag_exits_when_the_install_has_no_nightshift_service(
    mock_assert_docker: mock.MagicMock,
    mock_assert_installed: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
) -> None:
    with pytest.raises(typer.Exit):
        logs(directory=directory, follow=False, tail=20, nightshift=True)

    assert mock_run.call_count == 0


@mock.patch("deepfellow.server.logs.run")
@mock.patch("deepfellow.server.logs.echo.info")
@mock.patch("deepfellow.server.logs.assert_nightshift_installed")
@mock.patch("deepfellow.server.logs.assert_docker")
def test_logs_server_logs_do_not_require_a_nightshift_service(
    mock_assert_docker: mock.MagicMock,
    mock_assert_installed: mock.MagicMock,
    mock_info: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
) -> None:
    logs(directory=directory, follow=False, tail=20, nightshift=False)

    assert mock_assert_installed.call_count == 0
