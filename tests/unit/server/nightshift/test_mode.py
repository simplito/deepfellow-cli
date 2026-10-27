# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock

import pytest
import typer
from typer.testing import CliRunner

from deepfellow.common.defaults import NightshiftModeChoice
from deepfellow.server.nightshift.mode import app, mode

runner = CliRunner()


@mock.patch("deepfellow.server.nightshift.mode.apply_nightshift_schedule")
@mock.patch("deepfellow.server.nightshift.mode.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.nightshift.mode.assert_docker")
@mock.patch("deepfellow.server.nightshift.mode.check_server_directory")
@mock.patch("deepfellow.server.nightshift.mode.echo")
def test_mode_always_applies_the_mode_only(
    mock_echo: mock.MagicMock,
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_apply: mock.MagicMock,
    directory: Path,
) -> None:
    mode(mode=NightshiftModeChoice.always, start="22:00", stop="06:00", directory=directory)

    assert mock_apply.call_args == mock.call(directory, "always", "22:00", "06:00", {"DF_NIGHTSHIFT_MODE": "always"})
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.server.nightshift.mode.apply_nightshift_schedule")
@mock.patch("deepfellow.server.nightshift.mode.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.nightshift.mode.assert_systemd_available")
@mock.patch("deepfellow.server.nightshift.mode.assert_docker")
@mock.patch("deepfellow.server.nightshift.mode.check_server_directory")
@mock.patch("deepfellow.server.nightshift.mode.echo")
def test_mode_shift_applies_mode_and_hours_and_warns(
    mock_echo: mock.MagicMock,
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_assert_systemd: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_apply: mock.MagicMock,
    directory: Path,
) -> None:
    mode(mode=NightshiftModeChoice.shift, start="22:00", stop="06:00", directory=directory)

    assert mock_assert_systemd.call_count == 1
    assert mock_echo.warning.call_count == 1
    assert mock_apply.call_args == mock.call(
        directory,
        "shift",
        "22:00",
        "06:00",
        {"DF_NIGHTSHIFT_MODE": "shift", "DF_NIGHTSHIFT_START": "22:00", "DF_NIGHTSHIFT_STOP": "06:00"},
    )


@mock.patch("deepfellow.server.nightshift.mode.apply_nightshift_schedule")
@mock.patch("deepfellow.server.nightshift.mode.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.nightshift.mode.assert_docker")
@mock.patch("deepfellow.server.nightshift.mode.check_server_directory")
@mock.patch("deepfellow.server.nightshift.mode.assert_systemd_available")
@mock.patch("deepfellow.server.nightshift.mode.echo")
def test_mode_shift_checks_systemd_before_warning_or_applying(
    mock_echo: mock.MagicMock,
    mock_assert_systemd: mock.MagicMock,
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_apply: mock.MagicMock,
    directory: Path,
) -> None:
    """On a non-systemd host, assert_systemd_available() must abort before printing the "tasks
    wait in RabbitMQ" warning or applying anything - not limp through a doomed loginctl/sudo
    dance first."""
    mock_assert_systemd.side_effect = typer.Exit(1)

    with pytest.raises(typer.Exit):
        mode(mode=NightshiftModeChoice.shift, start="22:00", stop="06:00", directory=directory)

    assert mock_echo.warning.call_count == 0
    assert mock_apply.call_count == 0


@mock.patch("deepfellow.server.nightshift.mode.apply_nightshift_schedule")
@mock.patch("deepfellow.server.nightshift.mode.read_env_file_to_dict")
@mock.patch("deepfellow.server.nightshift.mode.assert_systemd_available")
@mock.patch("deepfellow.server.nightshift.mode.assert_docker")
@mock.patch("deepfellow.server.nightshift.mode.check_server_directory")
@mock.patch("deepfellow.server.nightshift.mode.echo")
def test_mode_shift_keeps_the_stored_hour_that_was_not_passed(
    mock_echo: mock.MagicMock,
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_assert_systemd: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_apply: mock.MagicMock,
    directory: Path,
) -> None:
    """`mode shift --start 21:00` (or a bare `mode shift` to repair the timers) must not reset the
    hour that wasn't passed back to 22:00/06:00 when .env already holds a custom one."""
    mock_read_env.return_value = {"df_nightshift_start": "23:00", "df_nightshift_stop": "05:00"}

    mode(mode=NightshiftModeChoice.shift, start="21:00", stop=None, directory=directory)

    assert mock_apply.call_args.args[:4] == (directory, "shift", "21:00", "05:00")


@mock.patch("deepfellow.server.nightshift.mode.apply_nightshift_schedule")
@mock.patch("deepfellow.server.nightshift.mode.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.nightshift.mode.assert_systemd_available")
@mock.patch("deepfellow.server.nightshift.mode.assert_docker")
@mock.patch("deepfellow.server.nightshift.mode.check_server_directory")
@mock.patch("deepfellow.server.nightshift.mode.echo")
def test_mode_shift_falls_back_to_default_hours_when_nothing_is_stored(
    mock_echo: mock.MagicMock,
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_assert_systemd: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_apply: mock.MagicMock,
    directory: Path,
) -> None:
    mode(mode=NightshiftModeChoice.shift, start=None, stop=None, directory=directory)

    assert mock_apply.call_args.args[:4] == (directory, "shift", "22:00", "06:00")


@mock.patch("deepfellow.server.nightshift.mode.apply_nightshift_schedule")
@mock.patch("deepfellow.server.nightshift.mode.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.nightshift.mode.assert_docker")
@mock.patch("deepfellow.server.nightshift.mode.check_server_directory")
@mock.patch("deepfellow.server.nightshift.mode.echo")
def test_mode_rejects_equal_start_and_stop(
    mock_echo: mock.MagicMock,
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_apply: mock.MagicMock,
    directory: Path,
) -> None:
    with pytest.raises(typer.BadParameter):
        mode(mode=NightshiftModeChoice.shift, start="22:00", stop="22:00", directory=directory)

    assert mock_apply.call_count == 0


@pytest.mark.parametrize("bad_option", ["--start", "--stop"])
def test_mode_cli_rejects_malformed_hour(bad_option: str) -> None:
    """--start/--stop had no format validation at all before - any non-empty string reached
    generate_nightshift_units()'s unguarded split(':') and crashed with a raw traceback."""
    result = runner.invoke(app, ["shift", bad_option, "not-a-time"])

    assert result.exit_code != 0
    assert "Invalid time" in result.output


@mock.patch("deepfellow.server.nightshift.mode.apply_nightshift_schedule")
@mock.patch(
    "deepfellow.server.nightshift.mode.read_env_file_to_dict",
    return_value={"df_nightshift_start": "garbage", "df_nightshift_stop": "25:99"},
)
@mock.patch("deepfellow.server.nightshift.mode.assert_docker")
@mock.patch("deepfellow.server.nightshift.mode.check_server_directory")
@mock.patch("deepfellow.server.nightshift.mode.echo")
def test_mode_always_is_not_blocked_by_malformed_stored_hours(
    mock_echo: mock.MagicMock,
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_apply: mock.MagicMock,
    directory: Path,
) -> None:
    """The hours aren't used outside `shift` - a hand-edited, broken value must not stop the admin
    from switching away from it."""
    mode(mode=NightshiftModeChoice.always, start=None, stop=None, directory=directory)

    assert mock_apply.call_count == 1
    assert mock_apply.call_args.args[1] == "always"
