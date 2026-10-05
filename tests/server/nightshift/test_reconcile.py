# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

import itertools
import shlex
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest
import typer
from typer.testing import CliRunner

from deepfellow.server.nightshift import app as nightshift_app
from deepfellow.server.nightshift.reconcile import DOCKER_WAIT_SECONDS, SERVER_WAIT_SECONDS, reconcile
from deepfellow.server.utils.systemd import generate_nightshift_units

runner = CliRunner()


@mock.patch("deepfellow.server.nightshift.reconcile.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.nightshift.reconcile.assert_docker")
@mock.patch("deepfellow.server.nightshift.reconcile.wait_for_docker", return_value=True)
@mock.patch("deepfellow.server.nightshift.reconcile.check_server_directory")
def test_reconcile_waits_for_docker_then_reconciles_running_state(
    mock_check: mock.MagicMock,
    mock_wait: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_reconcile: mock.MagicMock,
    directory: Path,
) -> None:
    reconcile(directory=directory)

    assert mock_wait.call_args == mock.call(DOCKER_WAIT_SECONDS)
    assert mock_reconcile.call_args == mock.call(directory, server_wait_seconds=SERVER_WAIT_SECONDS)


@mock.patch("deepfellow.server.nightshift.reconcile.echo")
@mock.patch("deepfellow.server.nightshift.reconcile.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.nightshift.reconcile.wait_for_docker", return_value=False)
@mock.patch("deepfellow.server.nightshift.reconcile.check_server_directory")
def test_reconcile_exits_without_touching_the_worker_when_docker_never_comes_up(
    mock_check: mock.MagicMock,
    mock_wait: mock.MagicMock,
    mock_reconcile: mock.MagicMock,
    mock_echo: mock.MagicMock,
    directory: Path,
) -> None:
    with pytest.raises(typer.Exit):
        reconcile(directory=directory)

    assert mock_echo.error.call_count == 1
    assert mock_reconcile.call_count == 0


def test_reconcile_is_hidden_from_help() -> None:
    result = runner.invoke(nightshift_app, ["--help"])

    assert result.exit_code == 0
    assert "reconcile" not in result.output


@pytest.mark.parametrize(
    ("hour", "worker_running", "server_running", "expected_docker_call"),
    [
        # inside the window, worker down, server up -> start, without pulling in dependencies
        (23, False, True, ["docker", "compose", "up", "-d", "--no-deps", "nightshift"]),
        (2, False, True, ["docker", "compose", "up", "-d", "--no-deps", "nightshift"]),  # after midnight, still inside
        (23, False, False, None),  # inside the window, but the server was stopped on purpose -> leave it alone
        (7, True, True, ["docker", "compose", "stop", "nightshift"]),  # outside the window, worker up -> stop
        (7, True, False, ["docker", "compose", "stop", "nightshift"]),  # stopping is safe even without the server
        (14, False, True, None),  # outside the window, worker already down -> nothing
        (23, True, True, None),  # inside the window, worker already up -> nothing (never interrupt it)
    ],
)
@pytest.mark.parametrize("service", ["nightshift-start.service", "nightshift-stop.service"])
@mock.patch("deepfellow.server.utils.docker.time.sleep")
@mock.patch("deepfellow.server.utils.docker.time.monotonic", side_effect=itertools.count(0, 60))
@mock.patch("deepfellow.server.utils.time.datetime")
@mock.patch("deepfellow.server.utils.docker.get_docker_network", return_value="net")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.is_service_running_or_raise")
@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.utils.docker.read_env_file_to_dict")
@mock.patch("deepfellow.server.nightshift.reconcile.assert_docker")
@mock.patch("deepfellow.server.nightshift.reconcile.wait_for_docker", return_value=True)
@mock.patch("deepfellow.server.nightshift.reconcile.check_server_directory")
def test_generated_unit_command_leaves_the_worker_in_the_right_state_for_the_current_time(
    mock_check: mock.MagicMock,
    mock_wait: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_has_nightshift: mock.MagicMock,
    mock_is_running: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_get_network: mock.MagicMock,
    mock_datetime: mock.MagicMock,
    mock_monotonic: mock.MagicMock,
    mock_sleep: mock.MagicMock,
    service: str,
    hour: int,
    worker_running: bool,
    server_running: bool,
    expected_docker_call: list[str] | None,
    tmp_path: Path,
) -> None:
    """Runs the exact command a timer's unit would run. Both the start and the stop service end up
    in the same, correct state - so a replayed missed trigger can't leave the worker running
    outside its 22:00-06:00 window, whichever order they fire in - and a stack that was stopped on
    purpose is never partly revived."""
    mock_read_env.return_value = {
        "df_nightshift_mode": "shift",
        "df_nightshift_start": "22:00",
        "df_nightshift_stop": "06:00",
    }
    mock_is_running.side_effect = lambda name, cwd: worker_running if name == "nightshift" else server_running
    units = generate_nightshift_units(tmp_path, "22:00", "06:00")
    exec_start = next(line for line in units[service].splitlines() if line.startswith("ExecStart="))
    arguments = shlex.split(exec_start.removeprefix("ExecStart="))
    arguments = arguments[arguments.index("nightshift") + 1 :]
    mock_datetime.now.return_value = datetime(2026, 1, 1, hour, 0, tzinfo=timezone.utc)

    result = runner.invoke(nightshift_app, arguments)

    assert result.exit_code == 0, result.output
    docker_calls = [call.args[0] for call in mock_run.call_args_list]
    assert docker_calls == ([expected_docker_call] if expected_docker_call else [])
