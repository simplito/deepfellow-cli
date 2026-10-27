# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock

import pytest
import typer

from deepfellow.server.utils.nightshift import apply_nightshift_schedule, validate_nightshift_schedule


@pytest.fixture(autouse=True)
def nightshift_installed():
    """These tests are about the schedule, not about whether the compose file has the worker."""
    with mock.patch("deepfellow.server.utils.nightshift.assert_nightshift_installed") as patched:
        yield patched


@pytest.mark.parametrize(
    ("mode", "start", "stop"),
    [
        ("always", "", ""),
        ("always", "22:00", "06:00"),
        ("always", "bad", "25:99"),
        ("always", "22:00", "22:00"),
        ("shift", "22:00", "06:00"),
        ("shift", "", ""),
        ("shift", "22:00", ""),
    ],
)
def test_validate_nightshift_schedule_accepts_valid_and_incomplete_combinations_and_ignores_hours_outside_shift(
    mode: str, start: str, stop: str
) -> None:
    validate_nightshift_schedule(mode, start, stop)


@pytest.mark.parametrize(
    ("mode", "start", "stop"),
    [
        ("Shift", "22:00", "06:00"),
        ("sometimes", "", ""),
        ("shift", "bad", "06:00"),
        ("shift", "22:00", "25:00"),
        ("shift", "22:00", "22:00"),
    ],
)
def test_validate_nightshift_schedule_rejects_what_timers_cannot_be_generated_from(
    mode: str, start: str, stop: str
) -> None:
    with pytest.raises(typer.BadParameter):
        validate_nightshift_schedule(mode, start, stop)


@mock.patch("deepfellow.server.utils.nightshift.echo")
@mock.patch("deepfellow.server.utils.nightshift.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.utils.nightshift.env_set")
@mock.patch("deepfellow.server.utils.nightshift.reconcile_nightshift_schedule")
def test_apply_nightshift_schedule_regenerates_timers_then_writes_env_then_reconciles_the_worker(
    mock_timers: mock.MagicMock,
    mock_env_set: mock.MagicMock,
    mock_running_state: mock.MagicMock,
    mock_echo: mock.MagicMock,
    directory: Path,
) -> None:
    """Timers first: a host that can't support them fails before .env is touched."""
    manager = mock.Mock()
    manager.attach_mock(mock_timers, "timers")
    manager.attach_mock(mock_env_set, "env_set")
    manager.attach_mock(mock_running_state, "running_state")

    apply_nightshift_schedule(
        directory, "shift", "22:00", "06:00", {"DF_NIGHTSHIFT_START": "22:00", "DF_NIGHTSHIFT_STOP": "06:00"}
    )

    assert manager.mock_calls == [
        mock.call.timers(directory, "shift", "22:00", "06:00"),
        mock.call.env_set(directory / ".env", "DF_NIGHTSHIFT_START", "22:00"),
        mock.call.env_set(directory / ".env", "DF_NIGHTSHIFT_STOP", "06:00"),
        mock.call.running_state(directory),
    ]
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.server.utils.nightshift.echo")
@mock.patch("deepfellow.server.utils.nightshift.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.utils.nightshift.env_set")
@mock.patch("deepfellow.server.utils.nightshift.reconcile_nightshift_schedule")
def test_apply_nightshift_schedule_removes_timers_for_always_mode(
    mock_timers: mock.MagicMock,
    mock_env_set: mock.MagicMock,
    mock_running_state: mock.MagicMock,
    mock_echo: mock.MagicMock,
    directory: Path,
) -> None:
    apply_nightshift_schedule(directory, "always", "", "", {"DF_NIGHTSHIFT_MODE": "always"})

    assert mock_timers.call_args == mock.call(directory, "always", "", "")
    assert mock_env_set.call_args_list == [mock.call(directory / ".env", "DF_NIGHTSHIFT_MODE", "always")]


@pytest.mark.parametrize(("start", "stop"), [("", ""), ("22:00", ""), ("", "06:00")])
@mock.patch("deepfellow.server.utils.nightshift.remove_nightshift_timers")
@mock.patch("deepfellow.server.utils.nightshift.echo")
@mock.patch("deepfellow.server.utils.nightshift.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.utils.nightshift.env_set")
@mock.patch("deepfellow.server.utils.nightshift.reconcile_nightshift_schedule")
def test_apply_nightshift_schedule_warns_removes_stale_timers_and_still_writes_when_shift_mode_has_no_complete_hours(
    mock_timers: mock.MagicMock,
    mock_env_set: mock.MagicMock,
    mock_running_state: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_remove_timers: mock.MagicMock,
    start: str,
    stop: str,
    directory: Path,
) -> None:
    """`env set` is an admin tool: shift without hours is written as given (no invented defaults),
    the admin is told what it means - no timers, so the worker behaves as always-on. Timers left
    from an earlier complete schedule are removed, or they would keep firing at the old hours."""
    apply_nightshift_schedule(directory, "shift", start, stop, {"DF_NIGHTSHIFT_MODE": "shift"})

    assert mock_echo.warning.call_count == 1
    assert mock_remove_timers.call_args == mock.call(directory)
    assert mock_timers.call_count == 0
    assert mock_env_set.call_args_list == [mock.call(directory / ".env", "DF_NIGHTSHIFT_MODE", "shift")]
    assert mock_running_state.call_args == mock.call(directory)


@mock.patch("deepfellow.server.utils.nightshift.echo")
@mock.patch("deepfellow.server.utils.nightshift.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.utils.nightshift.env_set")
@mock.patch("deepfellow.server.utils.nightshift.reconcile_nightshift_schedule")
def test_apply_nightshift_schedule_changes_nothing_when_the_values_are_invalid(
    mock_timers: mock.MagicMock,
    mock_env_set: mock.MagicMock,
    mock_running_state: mock.MagicMock,
    mock_echo: mock.MagicMock,
    directory: Path,
) -> None:
    with pytest.raises(typer.BadParameter):
        apply_nightshift_schedule(directory, "shift", "22:00", "22:00", {"DF_NIGHTSHIFT_STOP": "22:00"})

    assert mock_timers.call_count == 0
    assert mock_env_set.call_count == 0
    assert mock_running_state.call_count == 0


@mock.patch("deepfellow.server.utils.nightshift.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.utils.nightshift.env_set")
@mock.patch("deepfellow.server.utils.nightshift.reconcile_nightshift_schedule")
def test_apply_nightshift_schedule_changes_nothing_when_the_install_has_no_nightshift_service(
    mock_timers: mock.MagicMock,
    mock_env_set: mock.MagicMock,
    mock_running_state: mock.MagicMock,
    nightshift_installed: mock.MagicMock,
    directory: Path,
) -> None:
    """No worker to schedule: no timers for it and no `.env` keys nothing will ever read."""
    nightshift_installed.side_effect = typer.Exit(1)

    with pytest.raises(typer.Exit):
        apply_nightshift_schedule(directory, "shift", "22:00", "06:00", {"DF_NIGHTSHIFT_MODE": "shift"})

    assert nightshift_installed.call_args == mock.call(directory)
    assert mock_timers.call_count == 0
    assert mock_env_set.call_count == 0
    assert mock_running_state.call_count == 0
