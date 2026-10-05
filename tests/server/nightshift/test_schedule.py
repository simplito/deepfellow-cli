# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock

import pytest
import typer
from typer.testing import CliRunner

from deepfellow.server.nightshift.schedule import app, schedule

runner = CliRunner()


@mock.patch("deepfellow.server.nightshift.schedule.apply_nightshift_schedule")
@mock.patch("deepfellow.server.nightshift.schedule.read_env_file_to_dict")
@mock.patch("deepfellow.server.nightshift.schedule.assert_docker")
@mock.patch("deepfellow.server.nightshift.schedule.check_server_directory")
@mock.patch("deepfellow.server.nightshift.schedule.echo")
def test_schedule_applies_both_hours(
    mock_echo: mock.MagicMock,
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_apply: mock.MagicMock,
    directory: Path,
) -> None:
    mock_read_env.return_value = {"df_nightshift_mode": "shift"}

    schedule(start="23:00", stop="05:00", directory=directory)

    assert mock_apply.call_args == mock.call(
        directory, "shift", "23:00", "05:00", {"DF_NIGHTSHIFT_START": "23:00", "DF_NIGHTSHIFT_STOP": "05:00"}
    )
    assert mock_echo.success.call_count == 1


@pytest.mark.parametrize(
    ("start", "stop", "expected"),
    [(None, "05:00", ("22:00", "05:00")), ("23:00", None, ("23:00", "06:00"))],
    ids=["stop_only", "start_only"],
)
@mock.patch("deepfellow.server.nightshift.schedule.apply_nightshift_schedule")
@mock.patch("deepfellow.server.nightshift.schedule.read_env_file_to_dict")
@mock.patch("deepfellow.server.nightshift.schedule.assert_docker")
@mock.patch("deepfellow.server.nightshift.schedule.check_server_directory")
@mock.patch("deepfellow.server.nightshift.schedule.echo")
def test_schedule_keeps_the_stored_hour_that_was_not_passed(
    mock_echo: mock.MagicMock,
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_apply: mock.MagicMock,
    start: str | None,
    stop: str | None,
    expected: tuple[str, str],
    directory: Path,
) -> None:
    """Changing only one hour must not require re-typing the other."""
    mock_read_env.return_value = {
        "df_nightshift_mode": "shift",
        "df_nightshift_start": "22:00",
        "df_nightshift_stop": "06:00",
    }

    schedule(start=start, stop=stop, directory=directory)

    assert mock_apply.call_args.args[2:4] == expected


@mock.patch("deepfellow.server.nightshift.schedule.apply_nightshift_schedule")
@mock.patch("deepfellow.server.nightshift.schedule.read_env_file_to_dict")
@mock.patch("deepfellow.server.nightshift.schedule.assert_docker")
@mock.patch("deepfellow.server.nightshift.schedule.check_server_directory")
@mock.patch("deepfellow.server.nightshift.schedule.echo")
def test_schedule_shows_message_when_neither_flag_provided(
    mock_echo: mock.MagicMock,
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_apply: mock.MagicMock,
    directory: Path,
) -> None:
    schedule(start=None, stop=None, directory=directory)

    assert mock_echo.info.call_args == mock.call("Nothing to change - pass --start and/or --stop.")
    assert mock_read_env.call_count == 0
    assert mock_apply.call_count == 0


@mock.patch("deepfellow.server.nightshift.schedule.apply_nightshift_schedule")
@mock.patch("deepfellow.server.nightshift.schedule.read_env_file_to_dict")
@mock.patch("deepfellow.server.nightshift.schedule.assert_docker")
@mock.patch("deepfellow.server.nightshift.schedule.check_server_directory")
@mock.patch("deepfellow.server.nightshift.schedule.echo")
def test_schedule_rejected_when_in_always_mode(
    mock_echo: mock.MagicMock,
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_apply: mock.MagicMock,
    directory: Path,
) -> None:
    mock_read_env.return_value = {"df_nightshift_mode": "always"}

    with pytest.raises(typer.Exit):
        schedule(start="23:00", stop="05:00", directory=directory)

    assert mock_apply.call_count == 0
    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.server.nightshift.schedule.apply_nightshift_schedule")
@mock.patch("deepfellow.server.nightshift.schedule.read_env_file_to_dict")
@mock.patch("deepfellow.server.nightshift.schedule.assert_docker")
@mock.patch("deepfellow.server.nightshift.schedule.check_server_directory")
@mock.patch("deepfellow.server.nightshift.schedule.echo")
def test_schedule_reports_incomplete_env_schedule_instead_of_crashing(
    mock_echo: mock.MagicMock,
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_apply: mock.MagicMock,
    directory: Path,
) -> None:
    """Passing only --start while .env has no stop hour used to hand "" to the unit generator's
    split(":") and crash with a ValueError."""
    mock_read_env.return_value = {"df_nightshift_mode": "shift", "df_nightshift_start": "22:00"}

    with pytest.raises(typer.Exit):
        schedule(start="23:00", stop=None, directory=directory)

    assert mock_echo.error.call_count == 1
    assert mock_apply.call_count == 0


@pytest.mark.parametrize("bad_option", ["--start", "--stop"])
def test_schedule_cli_rejects_malformed_hour(bad_option: str) -> None:
    """--start/--stop had no format validation at all before - any non-empty string reached
    generate_nightshift_units()'s unguarded split(':') and crashed with a raw traceback."""
    result = runner.invoke(app, [bad_option, "not-a-time"])

    assert result.exit_code != 0
    assert "Invalid time" in result.output
