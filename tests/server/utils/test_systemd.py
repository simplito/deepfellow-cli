# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

import subprocess
from pathlib import Path
from unittest import mock

import pytest
import typer

from deepfellow.server.utils.systemd import (
    SudoLingerError,
    SystemdUserError,
    _config_home,
    _linger_enabled,
    _user_manager_reachable,
    assert_systemd_available,
    ensure_linger_enabled,
    generate_nightshift_units,
    install_nightshift_timers,
    is_systemd_available,
    reconcile_nightshift_schedule,
    remove_nightshift_timers,
)


@pytest.fixture
def runtime_dir(tmp_path: Path):
    """Pretend the host was booted with systemd: SYSTEMD_RUNTIME_DIR exists."""
    path = tmp_path / "run-systemd-system"
    path.mkdir()
    patcher = mock.patch("deepfellow.server.utils.systemd.SYSTEMD_RUNTIME_DIR", path)
    patcher.start()
    yield path
    patcher.stop()


@pytest.fixture
def no_runtime_dir(tmp_path: Path):
    """Pretend the host was NOT booted with systemd: SYSTEMD_RUNTIME_DIR doesn't exist."""
    patcher = mock.patch("deepfellow.server.utils.systemd.SYSTEMD_RUNTIME_DIR", tmp_path / "missing")
    patcher.start()
    yield
    patcher.stop()


@pytest.fixture
def unit_dir(tmp_path: Path):
    """Point SYSTEMD_USER_UNIT_DIR at an empty temp directory for the test's duration."""
    path = tmp_path / "systemd-user"
    path.mkdir()
    patcher = mock.patch("deepfellow.server.utils.systemd.SYSTEMD_USER_UNIT_DIR", path)
    patcher.start()
    yield path
    patcher.stop()


_DAEMON_RELOAD_CALL = mock.call(["systemctl", "--user", "daemon-reload"], raises=SystemdUserError, quiet=True)


def _exec_start(units: dict[str, str], service: str) -> str:
    return next(line for line in units[service].splitlines() if line.startswith("ExecStart="))


@mock.patch("deepfellow.server.utils.systemd.shutil.which", return_value="/opt/venv/bin/deepfellow")
def test_generate_nightshift_units_both_services_run_the_same_reconcile_command(mock_which):
    """A timer that blindly started or stopped on its trigger could fire in the wrong order when
    `Persistent=true` replays both missed triggers after downtime - both run the same reconcile."""
    units = generate_nightshift_units(Path("/srv/server"), "22:00", "06:00")

    start_exec = _exec_start(units, "nightshift-start.service")
    assert start_exec == ("ExecStart=/opt/venv/bin/deepfellow server nightshift reconcile --directory /srv/server")
    assert _exec_start(units, "nightshift-stop.service") == start_exec


@mock.patch("deepfellow.server.utils.systemd.sys.executable", "/opt/venv/bin/python")
@mock.patch("deepfellow.server.utils.systemd.shutil.which", return_value=None)
def test_generate_nightshift_units_falls_back_to_python_module_when_cli_not_on_path(mock_which):
    units = generate_nightshift_units(Path("/srv/server"), "22:00", "06:00")

    assert _exec_start(units, "nightshift-start.service") == (
        "ExecStart=/opt/venv/bin/python -m deepfellow.main server nightshift reconcile --directory /srv/server"
    )


@mock.patch("deepfellow.server.utils.systemd.shutil.which", return_value="/opt/venv/bin/deepfellow")
def test_generate_nightshift_units_quotes_and_escapes_the_directory(mock_which):
    units = generate_nightshift_units(Path("/srv/my server/100%"), "22:00", "06:00")

    assert _exec_start(units, "nightshift-start.service").endswith("--directory '/srv/my server/100%%'")


def test_generate_nightshift_units_leaves_time_for_the_docker_wait():
    units = generate_nightshift_units(Path("/srv/server"), "22:00", "06:00")

    assert "TimeoutStartSec=480" in units["nightshift-start.service"]
    assert "TimeoutStartSec=480" in units["nightshift-stop.service"]


def test_generate_nightshift_units_encodes_start_and_stop_hours():
    units = generate_nightshift_units(Path("/srv/server"), "23:30", "05:15")

    assert "OnCalendar=*-*-* 23:30:00" in units["nightshift-start.timer"]
    assert "OnCalendar=*-*-* 05:15:00" in units["nightshift-stop.timer"]


def test_generate_nightshift_units_sets_working_directory():
    units = generate_nightshift_units(Path("/srv/server"), "22:00", "06:00")

    assert "WorkingDirectory=/srv/server" in units["nightshift-start.service"]
    assert "WorkingDirectory=/srv/server" in units["nightshift-stop.service"]


def test_generate_nightshift_units_timers_are_persistent():
    units = generate_nightshift_units(Path("/srv/server"), "22:00", "06:00")

    assert "Persistent=true" in units["nightshift-start.timer"]
    assert "Persistent=true" in units["nightshift-stop.timer"]


@mock.patch("deepfellow.server.utils.systemd.echo")
@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=False)
def test_assert_systemd_available_exits_when_systemctl_missing(mock_is_command_available, mock_echo):
    with pytest.raises(typer.Exit):
        assert_systemd_available()

    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.server.utils.systemd.echo")
@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=True)
def test_assert_systemd_available_exits_when_host_was_not_booted_with_systemd(
    mock_is_command_available, mock_echo, no_runtime_dir
):
    """WSL2 without systemd and containers ship `systemctl` but have no running systemd."""
    with pytest.raises(typer.Exit):
        assert_systemd_available()

    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.server.utils.systemd.echo")
@mock.patch("deepfellow.server.utils.systemd.run", side_effect=SystemdUserError)
@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=True)
def test_assert_systemd_available_exits_when_user_manager_is_unreachable(
    mock_is_command_available, mock_run, mock_echo, runtime_dir: Path
):
    """In a `su`/`sudo -u` session there is no user bus: fail now, before anything is written."""
    with pytest.raises(typer.Exit):
        assert_systemd_available()

    assert mock_run.call_args == mock.call(
        ["systemctl", "--user", "show-environment"], raises=SystemdUserError, quiet=True
    )
    assert mock_echo.error.call_count == 1
    assert "user session" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.server.utils.systemd.run", return_value="")
@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=True)
def test_assert_systemd_available_passes_when_systemd_and_user_manager_are_there(
    mock_is_command_available, mock_run, runtime_dir: Path
):
    assert_systemd_available()  # no exception raised


@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=True)
def test_is_systemd_available_true_when_systemctl_present_and_host_booted_with_systemd(
    mock_is_command_available, runtime_dir: Path
):
    assert is_systemd_available() is True


@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=False)
def test_is_systemd_available_false_when_systemctl_missing(mock_is_command_available, runtime_dir: Path):
    assert is_systemd_available() is False


@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=True)
def test_is_systemd_available_false_when_host_was_not_booted_with_systemd(mock_is_command_available, no_runtime_dir):
    assert is_systemd_available() is False


@mock.patch("deepfellow.server.utils.systemd.run")
@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=True)
def test_install_nightshift_timers_writes_units_and_enables_them(
    mock_is_command_available, mock_run, tmp_path: Path, unit_dir: Path, runtime_dir: Path
):
    install_nightshift_timers(tmp_path, "22:00", "06:00")

    assert (unit_dir / "nightshift-start.service").is_file()
    assert (unit_dir / "nightshift-start.timer").is_file()
    assert (unit_dir / "nightshift-stop.service").is_file()
    assert (unit_dir / "nightshift-stop.timer").is_file()
    assert mock.call(["systemctl", "--user", "daemon-reload"]) in mock_run.call_args_list
    assert mock.call(["systemctl", "--user", "enable", "--now", "nightshift-start.timer"]) in mock_run.call_args_list
    assert mock.call(["systemctl", "--user", "enable", "--now", "nightshift-stop.timer"]) in mock_run.call_args_list


@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=True)
@mock.patch("deepfellow.server.utils.systemd.run")
def test_remove_nightshift_timers_is_noop_when_units_absent(mock_run, mock_is_command_available, unit_dir: Path):
    remove_nightshift_timers(Path("/srv/server"))

    assert mock_run.call_count == 0


@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=True)
@mock.patch("deepfellow.server.utils.systemd.run")
def test_remove_nightshift_timers_disables_and_deletes_when_present(
    mock_run, mock_is_command_available, unit_dir: Path
):
    unit_names = (
        "nightshift-start.service",
        "nightshift-start.timer",
        "nightshift-stop.service",
        "nightshift-stop.timer",
    )
    for name in unit_names:
        (unit_dir / name).write_text("placeholder")

    remove_nightshift_timers(Path("/srv/server"))

    assert not (unit_dir / "nightshift-start.timer").exists()
    assert not (unit_dir / "nightshift-start.service").exists()
    assert not (unit_dir / "nightshift-stop.timer").exists()
    assert not (unit_dir / "nightshift-stop.service").exists()
    assert mock_run.call_args == _DAEMON_RELOAD_CALL


@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=True)
@mock.patch("deepfellow.server.utils.systemd.run")
def test_remove_nightshift_timers_cleans_up_stray_service_file_without_timer(
    mock_run, mock_is_command_available, unit_dir: Path
):
    """A .timer file can already be gone (an earlier interrupted cleanup, or a manual delete)
    while its .service file is left behind - the no-op guard must not only check for .timer
    files, or it returns early and leaks the stray .service file forever."""
    (unit_dir / "nightshift-start.service").write_text("placeholder")

    remove_nightshift_timers(Path("/srv/server"))

    assert not (unit_dir / "nightshift-start.service").exists()


@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=False)
@mock.patch("deepfellow.server.utils.systemd.run")
def test_remove_nightshift_timers_is_noop_when_systemctl_missing(mock_run, mock_is_command_available, unit_dir: Path):
    (unit_dir / "nightshift-start.timer").write_text("placeholder")

    remove_nightshift_timers(Path("/srv/server"))

    assert mock_run.call_count == 0
    assert (unit_dir / "nightshift-start.timer").exists()


SHOW_USER = ["loginctl", "show-user", "alice", "--property=Linger", "--value"]
ENABLE = ["loginctl", "enable-linger", "alice"]


@mock.patch("deepfellow.server.utils.systemd.getpass.getuser", return_value="alice")
@mock.patch("deepfellow.server.utils.systemd.echo")
@mock.patch("deepfellow.server.utils.systemd.run")
def test_ensure_linger_enabled_does_nothing_when_linger_is_already_on(mock_run, mock_echo, mock_getuser):
    """Checked first, so a second call (apply() after resolve() already enabled it) can never prompt."""
    mock_run.side_effect = ["yes\n"]

    ensure_linger_enabled()

    assert [call.args[0] for call in mock_run.call_args_list] == [SHOW_USER]
    assert mock_echo.warning.call_count == 0
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.server.utils.systemd.getpass.getuser", return_value="alice")
@mock.patch("deepfellow.server.utils.systemd.run")
def test_ensure_linger_enabled_succeeds_without_sudo(mock_run, mock_getuser):
    mock_run.side_effect = ["no\n", None]

    ensure_linger_enabled()

    assert [call.args[0] for call in mock_run.call_args_list] == [SHOW_USER, ENABLE]


@mock.patch("deepfellow.server.utils.systemd.getpass.getuser", return_value="alice")
@mock.patch("deepfellow.server.utils.systemd.run")
def test_ensure_linger_enabled_treats_a_failing_state_check_as_not_enabled(mock_run, mock_getuser):
    """`loginctl show-user` fails for a user that isn't logged in or lingering."""
    mock_run.side_effect = [SudoLingerError("User 1000 is not logged in or lingering"), None]

    ensure_linger_enabled()

    assert [call.args[0] for call in mock_run.call_args_list] == [SHOW_USER, ENABLE]


@mock.patch("deepfellow.server.utils.systemd.getpass.getuser", return_value="alice")
@mock.patch("deepfellow.server.utils.systemd.state", mock.Mock(yes=False, non_interactive=False))
@mock.patch("deepfellow.server.utils.systemd.echo")
@mock.patch("deepfellow.server.utils.systemd.run")
def test_ensure_linger_enabled_lets_sudo_ask_for_the_password_when_interactive(mock_run, mock_echo, mock_getuser):
    """No `-n`: sudo prompts on the terminal itself (this process never sees the password)."""
    mock_run.side_effect = ["no\n", SudoLingerError("denied"), None]
    mock_echo.confirm.return_value = True

    ensure_linger_enabled()

    assert mock_run.call_args_list[-1].args[0] == ["sudo", *ENABLE]


@mock.patch("deepfellow.server.utils.systemd.getpass.getuser", return_value="alice")
@mock.patch("deepfellow.server.utils.systemd.state", mock.Mock(yes=True, non_interactive=True))
@mock.patch("deepfellow.server.utils.systemd.echo")
@mock.patch("deepfellow.server.utils.systemd.run")
def test_ensure_linger_enabled_never_prompts_for_a_password_when_non_interactive(mock_run, mock_echo, mock_getuser):
    mock_run.side_effect = ["no\n", SudoLingerError("denied"), None]

    ensure_linger_enabled()

    assert mock_run.call_args_list[-1].args[0] == ["sudo", "-n", *ENABLE]
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.server.utils.systemd.getpass.getuser", return_value="alice")
@mock.patch("deepfellow.server.utils.systemd.state", mock.Mock(yes=False, non_interactive=False))
@mock.patch("deepfellow.server.utils.systemd.echo")
@mock.patch("deepfellow.server.utils.systemd.run")
def test_ensure_linger_enabled_exits_when_sudo_also_fails(mock_run, mock_echo, mock_getuser):
    mock_run.side_effect = ["no\n", SudoLingerError("denied"), SudoLingerError("still denied")]
    mock_echo.confirm.return_value = True

    with pytest.raises(typer.Exit):
        ensure_linger_enabled()

    assert "Run manually: sudo loginctl enable-linger alice" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.server.utils.systemd.getpass.getuser", return_value="alice")
@mock.patch("deepfellow.server.utils.systemd.state", mock.Mock(yes=False, non_interactive=False))
@mock.patch("deepfellow.server.utils.systemd.echo")
@mock.patch("deepfellow.server.utils.systemd.run")
def test_ensure_linger_enabled_exits_when_user_declines_sudo_retry(mock_run, mock_echo, mock_getuser):
    mock_run.side_effect = ["no\n", SudoLingerError("denied")]
    mock_echo.confirm.return_value = False

    with pytest.raises(typer.Exit):
        ensure_linger_enabled()

    assert mock_run.call_count == 2


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (subprocess.CompletedProcess(SHOW_USER, 0, stdout="yes\n", stderr=""), True),
        (subprocess.CompletedProcess(SHOW_USER, 0, stdout="no\n", stderr=""), False),
        (subprocess.CalledProcessError(1, SHOW_USER, stderr="not logged in or lingering"), False),
    ],
    ids=["enabled", "disabled", "unknown_user"],
)
@mock.patch("deepfellow.server.utils.systemd.getpass.getuser", return_value="alice")
@mock.patch("deepfellow.common.system.subprocess.run")
def test_linger_state_check_works_through_the_real_run_helper(mock_subprocess_run, mock_getuser, result, expected):
    if isinstance(result, Exception):
        mock_subprocess_run.side_effect = result
    else:
        mock_subprocess_run.return_value = result

    assert _linger_enabled("alice") is expected


@mock.patch("deepfellow.server.utils.systemd.assert_systemd_available")
@mock.patch("deepfellow.server.utils.systemd.install_nightshift_timers")
@mock.patch("deepfellow.server.utils.systemd.ensure_linger_enabled")
@mock.patch("deepfellow.server.utils.systemd.remove_nightshift_timers")
def test_reconcile_nightshift_schedule_shift_installs_timers(
    mock_remove_timers: mock.MagicMock,
    mock_ensure_linger: mock.MagicMock,
    mock_install_timers: mock.MagicMock,
    mock_assert_systemd: mock.MagicMock,
    tmp_path: Path,
) -> None:
    reconcile_nightshift_schedule(tmp_path, "shift", "22:00", "06:00")

    assert mock_assert_systemd.call_count == 1
    assert mock_ensure_linger.call_count == 1
    assert mock_install_timers.call_count == 1
    assert mock_install_timers.call_args == mock.call(tmp_path, "22:00", "06:00")
    assert mock_remove_timers.call_count == 0


@mock.patch("deepfellow.server.utils.systemd.assert_systemd_available")
@mock.patch("deepfellow.server.utils.systemd.ensure_linger_enabled")
@mock.patch("deepfellow.server.utils.systemd.install_nightshift_timers")
def test_reconcile_nightshift_schedule_shift_checks_systemd_before_linger(
    mock_install_timers: mock.MagicMock,
    mock_ensure_linger: mock.MagicMock,
    mock_assert_systemd: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """assert_systemd_available() must run before ensure_linger_enabled() - otherwise a
    non-systemd host (e.g. macOS) limps through a doomed loginctl/sudo dance before failing for
    the wrong reason."""
    call_order: list[str] = []
    mock_assert_systemd.side_effect = lambda: call_order.append("assert_systemd")
    mock_ensure_linger.side_effect = lambda: call_order.append("ensure_linger")

    reconcile_nightshift_schedule(tmp_path, "shift", "22:00", "06:00")

    assert call_order == ["assert_systemd", "ensure_linger"]


@mock.patch("deepfellow.server.utils.systemd.install_nightshift_timers")
@mock.patch("deepfellow.server.utils.systemd.ensure_linger_enabled")
@mock.patch("deepfellow.server.utils.systemd.remove_nightshift_timers")
def test_reconcile_nightshift_schedule_always_removes_timers(
    mock_remove_timers: mock.MagicMock,
    mock_ensure_linger: mock.MagicMock,
    mock_install_timers: mock.MagicMock,
    tmp_path: Path,
) -> None:
    reconcile_nightshift_schedule(tmp_path, "always", "", "")

    assert mock_remove_timers.call_args == mock.call(tmp_path)
    assert mock_ensure_linger.call_count == 0
    assert mock_install_timers.call_count == 0


@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=True)
@mock.patch("deepfellow.server.utils.systemd.run")
def test_remove_nightshift_timers_removes_units_that_belong_to_this_install(
    mock_run, mock_is_command_available, unit_dir: Path
):
    for filename, content in generate_nightshift_units(Path("/srv/server"), "22:00", "06:00").items():
        (unit_dir / filename).write_text(content)

    remove_nightshift_timers(Path("/srv/server"))

    assert list(unit_dir.iterdir()) == []
    assert mock_run.call_args == _DAEMON_RELOAD_CALL


@mock.patch("deepfellow.server.utils.systemd.echo")
@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=True)
@mock.patch("deepfellow.server.utils.systemd.run")
def test_remove_nightshift_timers_leaves_units_that_belong_to_another_install(
    mock_run, mock_is_command_available, mock_echo, unit_dir: Path
):
    """The unit names are global: after moving to a new --directory, uninstalling/pruning the OLD
    one must not stop the live install's schedule."""
    for filename, content in generate_nightshift_units(Path("/srv/new-install"), "22:00", "06:00").items():
        (unit_dir / filename).write_text(content)

    remove_nightshift_timers(Path("/srv/old-install"))

    assert len(list(unit_dir.iterdir())) == 4
    assert mock_run.call_count == 0
    assert mock_echo.info.call_count == 1
    assert "/srv/new-install" in mock_echo.info.call_args.args[0]


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (subprocess.CompletedProcess(["systemctl"], 0, stdout="", stderr=""), True),
        (subprocess.CalledProcessError(1, ["systemctl"], stderr="Failed to connect to bus"), False),
    ],
    ids=["reachable", "unreachable"],
)
@mock.patch("deepfellow.common.system.subprocess.run")
def test_user_manager_reachable_works_through_the_real_run_helper(mock_subprocess_run, side_effect, expected):
    """run() refuses `quiet=True` together with `capture_output=True` (SystemError) - a mocked run()
    can't catch that, so exercise the real one with only subprocess.run mocked."""
    mock_subprocess_run.side_effect = [side_effect] if isinstance(side_effect, Exception) else None
    mock_subprocess_run.return_value = None if isinstance(side_effect, Exception) else side_effect

    assert _user_manager_reachable() is expected


@mock.patch("deepfellow.server.utils.systemd.echo")
@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=True)
@mock.patch("deepfellow.server.utils.systemd.run")
def test_remove_nightshift_timers_survives_a_failing_daemon_reload(
    mock_run, mock_is_command_available, mock_echo, unit_dir: Path
):
    """The unit files are already deleted by then - an unreachable user manager must not abort
    `uninstall`/`prune` before they remove the install directory."""
    for filename, content in generate_nightshift_units(Path("/srv/server"), "22:00", "06:00").items():
        (unit_dir / filename).write_text(content)

    def fail_on_daemon_reload(command: list[str], **kwargs: object) -> None:
        if "daemon-reload" in command:
            raise SystemdUserError("Failed to connect to bus")

    mock_run.side_effect = fail_on_daemon_reload

    remove_nightshift_timers(Path("/srv/server"))

    assert list(unit_dir.iterdir()) == []
    assert mock_echo.warning.call_count == 1
    assert "daemon-reload" in mock_echo.warning.call_args.args[0]


def test_generate_nightshift_units_escapes_percent_in_the_working_directory():
    """systemd expands `%` specifiers in WorkingDirectory= as well, not only in ExecStart=."""
    units = generate_nightshift_units(Path("/srv/100%/server"), "22:00", "06:00")

    assert "WorkingDirectory=/srv/100%%/server" in units["nightshift-start.service"]


@mock.patch("deepfellow.server.utils.systemd.echo")
@mock.patch("deepfellow.server.utils.systemd.is_command_available", return_value=True)
@mock.patch("deepfellow.server.utils.systemd.run")
def test_remove_nightshift_timers_recognizes_its_own_directory_containing_a_percent(
    mock_run, mock_is_command_available, mock_echo, unit_dir: Path
):
    """The escaped `%%` read back from the unit is the same directory, not a foreign install."""
    directory = Path("/srv/100%/server")
    for filename, content in generate_nightshift_units(directory, "22:00", "06:00").items():
        (unit_dir / filename).write_text(content)

    remove_nightshift_timers(directory)

    assert list(unit_dir.iterdir()) == []
    assert mock_echo.info.call_count == 0


@pytest.mark.parametrize(
    ("xdg_config_home", "expected"),
    [
        ("/custom/config", Path("/custom/config")),
        ("", Path("/home/someone/.config")),
        ("relative/config", Path("/home/someone/.config")),  # the XDG spec says to ignore a relative value
    ],
)
@mock.patch("deepfellow.server.utils.systemd.Path.home", return_value=Path("/home/someone"))
def test_config_home_follows_xdg_config_home_like_systemd_does(
    mock_home, xdg_config_home: str, expected: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("XDG_CONFIG_HOME", xdg_config_home)

    assert _config_home() == expected


@mock.patch("deepfellow.server.utils.systemd.Path.home", return_value=Path("/home/someone"))
def test_config_home_defaults_to_dot_config_when_xdg_config_home_is_unset(mock_home, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    assert _config_home() == Path("/home/someone/.config")
