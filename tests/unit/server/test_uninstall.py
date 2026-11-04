# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

from deepfellow.common.config import read_env_file, save_env_file
from deepfellow.common.state import state
from deepfellow.server.uninstall import uninstall


@mock.patch("deepfellow.server.uninstall.echo")
@mock.patch("deepfellow.server.uninstall.set_default_server_directory")
@mock.patch("deepfellow.server.uninstall.get_default_server_directory")
@mock.patch("deepfellow.server.uninstall.rmtree")
@mock.patch("deepfellow.server.uninstall.run")
@mock.patch("deepfellow.server.uninstall.assert_docker")
@mock.patch("deepfellow.server.uninstall.check_server_directory")
def test_uninstall_checks_server_directory(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    mock_get_default_server_directory.return_value = Path("/other/dir")

    uninstall(directory=directory)

    assert mock_check_server_directory.call_count == 1
    assert mock_check_server_directory.call_args == mock.call(directory)


@mock.patch("deepfellow.server.uninstall.echo")
@mock.patch("deepfellow.server.uninstall.set_default_server_directory")
@mock.patch("deepfellow.server.uninstall.get_default_server_directory")
@mock.patch("deepfellow.server.uninstall.rmtree")
@mock.patch("deepfellow.server.uninstall.run")
@mock.patch("deepfellow.server.uninstall.assert_docker")
@mock.patch("deepfellow.server.uninstall.check_server_directory")
def test_uninstall_removes_containers_before_removing_files(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    mock_get_default_server_directory.return_value = Path("/other/dir")
    _mock_manager = Mock()
    _mock_manager.attach_mock(mock_run, "run")
    _mock_manager.attach_mock(mock_rmtree, "rmtree")

    uninstall(directory=directory)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "rm", "-s", "-f"], directory, quiet=True)
    assert mock_rmtree.call_count == 1
    assert mock_rmtree.call_args == mock.call(directory)
    assert _mock_manager.mock_calls == [
        mock.call.run(["docker", "compose", "rm", "-s", "-f"], directory, quiet=True),
        mock.call.rmtree(directory),
    ]


@mock.patch("deepfellow.server.uninstall.echo")
@mock.patch("deepfellow.server.uninstall.set_default_server_directory")
@mock.patch("deepfellow.server.uninstall.get_default_server_directory")
@mock.patch("deepfellow.server.uninstall.rmtree")
@mock.patch("deepfellow.server.uninstall.run")
@mock.patch("deepfellow.server.uninstall.assert_docker")
@mock.patch("deepfellow.server.uninstall.check_server_directory")
def test_uninstall_resets_default_server_directory_when_matching(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    mock_get_default_server_directory.return_value = directory

    uninstall(directory=directory)

    assert mock_set_default_server_directory.call_count == 1
    assert mock_set_default_server_directory.call_args == mock.call("", True)


@mock.patch("deepfellow.server.uninstall.echo")
@mock.patch("deepfellow.server.uninstall.set_default_server_directory")
@mock.patch("deepfellow.server.uninstall.get_default_server_directory")
@mock.patch("deepfellow.server.uninstall.rmtree")
@mock.patch("deepfellow.server.uninstall.run")
@mock.patch("deepfellow.server.uninstall.assert_docker")
@mock.patch("deepfellow.server.uninstall.check_server_directory")
def test_uninstall_keeps_default_server_directory_when_not_matching(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    mock_get_default_server_directory.return_value = Path("/other/dir")

    uninstall(directory=directory)

    assert mock_set_default_server_directory.call_count == 0


@mock.patch("deepfellow.server.uninstall.echo")
@mock.patch("deepfellow.server.uninstall.set_default_server_directory")
@mock.patch("deepfellow.server.uninstall.get_default_server_directory")
@mock.patch("deepfellow.server.uninstall.rmtree")
@mock.patch("deepfellow.server.uninstall.run")
@mock.patch("deepfellow.server.uninstall.assert_docker")
@mock.patch("deepfellow.server.uninstall.check_server_directory")
def test_uninstall_reports_success(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    mock_get_default_server_directory.return_value = Path("/other/dir")

    uninstall(directory=directory)

    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == mock.call("DeepFellow Server uninstalled.")


@mock.patch("deepfellow.server.uninstall.echo")
@mock.patch("deepfellow.server.uninstall.set_default_server_directory")
@mock.patch("deepfellow.server.uninstall.get_default_server_directory")
@mock.patch("deepfellow.server.uninstall.remove_nightshift_timers")
@mock.patch("deepfellow.server.uninstall.rmtree")
@mock.patch("deepfellow.server.uninstall.run")
@mock.patch("deepfellow.server.uninstall.assert_docker")
@mock.patch("deepfellow.server.uninstall.check_server_directory")
def test_uninstall_removes_nightshift_systemd_timers_before_removing_files(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_remove_nightshift_timers: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    mock_get_default_server_directory.return_value = Path("/other/dir")
    _mock_manager = Mock()
    _mock_manager.attach_mock(mock_remove_nightshift_timers, "remove_nightshift_timers")
    _mock_manager.attach_mock(mock_rmtree, "rmtree")

    uninstall(directory=directory)

    assert mock_remove_nightshift_timers.call_count == 1
    assert mock_remove_nightshift_timers.call_args == mock.call(directory)
    assert _mock_manager.mock_calls == [
        mock.call.remove_nightshift_timers(directory),
        mock.call.rmtree(directory),
    ]


@mock.patch("deepfellow.server.uninstall.echo")
@mock.patch("deepfellow.server.uninstall.set_default_server_directory")
@mock.patch("deepfellow.server.uninstall.get_default_server_directory")
@mock.patch("deepfellow.server.uninstall.rmtree")
@mock.patch("deepfellow.server.uninstall.run")
@mock.patch("deepfellow.server.uninstall.assert_docker")
@mock.patch("deepfellow.server.uninstall.check_server_directory")
def test_uninstall_clears_stored_server_url_when_matching(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    tmp_path: Path,
) -> None:
    directory = tmp_path / "server"
    directory.mkdir()
    save_env_file(directory / ".env", {"DF_SERVER_URL": "http://localhost:8000"})
    mock_get_default_server_directory.return_value = Path("/other/dir")
    save_env_file(state.cli_config_file, {"DF_SERVER_URL": "http://localhost:8000", "DF_OTHER": "kept"})
    state.cli_config = {"df_server_url": "http://localhost:8000"}

    uninstall(directory=directory)

    assert read_env_file(state.cli_config_file) == {"DF_OTHER": "kept"}
    assert "df_server_url" not in state.cli_config


@mock.patch("deepfellow.server.uninstall.echo")
@mock.patch("deepfellow.server.uninstall.set_default_server_directory")
@mock.patch("deepfellow.server.uninstall.get_default_server_directory")
@mock.patch("deepfellow.server.uninstall.rmtree")
@mock.patch("deepfellow.server.uninstall.run")
@mock.patch("deepfellow.server.uninstall.assert_docker")
@mock.patch("deepfellow.server.uninstall.check_server_directory")
def test_uninstall_keeps_stored_server_url_when_not_matching(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    tmp_path: Path,
) -> None:
    directory = tmp_path / "server"
    directory.mkdir()
    save_env_file(directory / ".env", {"DF_SERVER_URL": "http://localhost:8000"})
    mock_get_default_server_directory.return_value = Path("/other/dir")
    save_env_file(state.cli_config_file, {"DF_SERVER_URL": "http://remote:9000"})
    state.cli_config = {"df_server_url": "http://remote:9000"}

    uninstall(directory=directory)

    assert read_env_file(state.cli_config_file)["DF_SERVER_URL"] == "http://remote:9000"
    assert state.cli_config["df_server_url"] == "http://remote:9000"


@mock.patch("deepfellow.server.uninstall.save_env_file", side_effect=OSError("read-only"))
@mock.patch("deepfellow.server.uninstall.echo")
@mock.patch("deepfellow.server.uninstall.set_default_server_directory")
@mock.patch("deepfellow.server.uninstall.get_default_server_directory")
@mock.patch("deepfellow.server.uninstall.rmtree")
@mock.patch("deepfellow.server.uninstall.run")
@mock.patch("deepfellow.server.uninstall.assert_docker")
@mock.patch("deepfellow.server.uninstall.check_server_directory")
def test_uninstall_warns_and_finishes_when_stored_server_url_cannot_be_cleared(
    mock_check_server_directory: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_get_default_server_directory: Mock,
    mock_set_default_server_directory: Mock,
    mock_echo: Mock,
    mock_save_env_file: Mock,
    tmp_path: Path,
) -> None:
    directory = tmp_path / "server"
    directory.mkdir()
    (directory / ".env").write_text("DF_SERVER_URL=http://localhost:8000\n")
    mock_get_default_server_directory.return_value = Path("/other/dir")
    state.cli_config = {"df_server_url": "http://localhost:8000"}

    uninstall(directory=directory)

    assert mock_echo.warning.call_count == 1
    assert mock_echo.success.call_count == 1
