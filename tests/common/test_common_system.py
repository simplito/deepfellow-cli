# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for common/system.py."""

import subprocess
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.state import state
from deepfellow.common.system import SudoRemoveError, check_service_directory, is_command_available, rmtree, run


class _CustomError(Exception):
    """Custom exception used to exercise the `raises=` kwarg."""


@mock.patch("deepfellow.common.system.subprocess.run")
def test_run_returns_stdout_on_success(mock_subprocess_run: Mock, directory: Path) -> None:
    mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="output")

    result = run(["echo", "hi"], cwd=directory)

    assert result == "output"


@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.subprocess.run")
def test_run_called_process_error_raises_custom_exception(
    mock_subprocess_run: Mock, mock_echo: Mock, directory: Path
) -> None:
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, ["cmd"], stderr="boom")

    with pytest.raises(_CustomError, match="boom"):
        run(["cmd"], cwd=directory, raises=_CustomError)

    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.subprocess.run")
def test_run_called_process_error_without_raises_echoes_stderr_and_exits(
    mock_subprocess_run: Mock, mock_echo: Mock, directory: Path
) -> None:
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, ["cmd"], stderr="something failed")

    with pytest.raises(typer.Exit):
        run(["cmd"], cwd=directory)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("something failed")


@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.subprocess.run")
def test_run_called_process_error_in_debug_mode_reraises(
    mock_subprocess_run: Mock, mock_echo: Mock, directory: Path
) -> None:
    exc = subprocess.CalledProcessError(1, ["cmd"], stderr="something failed")
    mock_subprocess_run.side_effect = exc
    state.debug = True

    with pytest.raises(subprocess.CalledProcessError):
        run(["cmd"], cwd=directory)


@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.subprocess.run")
def test_run_os_error_raises_custom_exception(mock_subprocess_run: Mock, mock_echo: Mock, directory: Path) -> None:
    mock_subprocess_run.side_effect = FileNotFoundError(2, "No such file or directory")

    with pytest.raises(_CustomError):
        run(["docker", "compose", "pull"], cwd=directory, raises=_CustomError)

    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.subprocess.run")
def test_run_os_error_without_raises_echoes_error_and_exits(
    mock_subprocess_run: Mock, mock_echo: Mock, directory: Path
) -> None:
    mock_subprocess_run.side_effect = FileNotFoundError(2, "No such file or directory")

    with pytest.raises(typer.Exit):
        run(["docker", "compose", "pull"], cwd=directory)

    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.subprocess.run")
def test_run_os_error_in_debug_mode_reraises(mock_subprocess_run: Mock, mock_echo: Mock, directory: Path) -> None:
    exc = PermissionError(13, "Permission denied")
    mock_subprocess_run.side_effect = exc
    state.debug = True

    with pytest.raises(PermissionError):
        run(["docker", "compose", "pull"], cwd=directory)


def test_run_quiet_and_capture_output_raises_system_error(directory: Path) -> None:
    with pytest.raises(SystemError, match="ERROR: If quiet then not capture_output"):
        run(["cmd"], cwd=directory, quiet=True, capture_output=True)


@mock.patch("deepfellow.common.system.subprocess.run")
def test_run_quiet_sets_devnull_stdout_and_pipe_stderr(mock_subprocess_run: Mock, directory: Path) -> None:
    mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=None)

    run(["cmd"], cwd=directory, quiet=True)

    assert mock_subprocess_run.call_count == 1
    assert mock_subprocess_run.call_args.kwargs["stdout"] == subprocess.DEVNULL
    assert mock_subprocess_run.call_args.kwargs["stderr"] == subprocess.PIPE


@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.subprocess.run")
def test_run_called_process_error_with_empty_stderr_skips_echo_error(
    mock_subprocess_run: Mock, mock_echo: Mock, directory: Path
) -> None:
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, ["cmd"], stderr="")

    with pytest.raises(typer.Exit):
        run(["cmd"], cwd=directory)

    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.subprocess.run")
def test_run_called_process_error_with_only_warning_lines_skips_echo_error(
    mock_subprocess_run: Mock, mock_echo: Mock, directory: Path
) -> None:
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        1, ["cmd"], stderr="level=warning: careful\nlevel=info: fyi"
    )

    with pytest.raises(typer.Exit):
        run(["cmd"], cwd=directory)

    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.common.system.shutil.which")
def test_is_command_available_returns_true_when_found(mock_which: Mock) -> None:
    mock_which.return_value = "/usr/bin/docker"

    result = is_command_available("docker")

    assert result is True
    assert mock_which.call_args == mock.call("docker")


@mock.patch("deepfellow.common.system.shutil.which")
def test_is_command_available_returns_false_when_not_found(mock_which: Mock) -> None:
    mock_which.return_value = None

    result = is_command_available("nonexistent")

    assert result is False


def test_check_service_directory_does_nothing_when_directory_exists(tmp_path: Path) -> None:
    check_service_directory(tmp_path, "infra")


@mock.patch("deepfellow.common.system.echo")
def test_check_service_directory_raises_exit_when_directory_missing(mock_echo: Mock, tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(typer.Exit):
        check_service_directory(missing, "infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Create Deepfellow infra first.")


@mock.patch("deepfellow.common.system.echo")
def test_check_service_directory_uses_custom_missing_message_when_given(mock_echo: Mock, tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(typer.Exit):
        check_service_directory(missing, "infra", missing_message="custom message")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("custom message")


@mock.patch("deepfellow.common.system.shutil.rmtree")
def test_rmtree_success(mock_shutil_rmtree: Mock, directory: Path) -> None:
    rmtree(directory)

    assert mock_shutil_rmtree.call_count == 1
    assert mock_shutil_rmtree.call_args == mock.call(directory)


@mock.patch("deepfellow.common.system.run")
@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.shutil.rmtree")
def test_rmtree_permission_error_yes_flag_sudo_succeeds(
    mock_shutil_rmtree: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_shutil_rmtree.side_effect = PermissionError
    mock_run.return_value = ""
    state.yes = True

    rmtree(directory)

    assert mock_echo.confirm.call_count == 0
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(
        ["sudo", "-n", "rm", "-rf", directory.as_posix()], raises=SudoRemoveError, quiet=True
    )


@mock.patch("deepfellow.common.system.run")
@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.shutil.rmtree")
def test_rmtree_permission_error_user_confirms_sudo_succeeds(
    mock_shutil_rmtree: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_shutil_rmtree.side_effect = PermissionError
    mock_echo.confirm.return_value = True
    mock_run.return_value = ""

    rmtree(directory)

    assert mock_echo.confirm.call_count == 1
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(
        ["sudo", "-n", "rm", "-rf", directory.as_posix()], raises=SudoRemoveError, quiet=True
    )


@mock.patch("deepfellow.common.system.run")
@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.shutil.rmtree")
def test_rmtree_permission_error_sudo_fails_raises_exit(
    mock_shutil_rmtree: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_shutil_rmtree.side_effect = PermissionError
    mock_echo.confirm.return_value = True
    mock_run.side_effect = SudoRemoveError("sudo: interactive authentication is required")

    with pytest.raises(typer.Exit):
        rmtree(directory)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        f"sudo rm -rf failed. Remove manually: sudo rm -rf {directory.as_posix()}"
    )


@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.subprocess.run")
@mock.patch("deepfellow.common.system.shutil.rmtree")
def test_rmtree_sudo_interactive_auth_required_raises_exit_with_remediation(
    mock_shutil_rmtree: Mock,
    mock_subprocess_run: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    """Regression test: exercises the real `run()`, not a mock of it.

    Mocking `run()` directly (as the other rmtree tests do) hid a real bug where `rmtree()`
    checked `run(...) is None` to detect failure - a contract `run()` never actually honors, since
    it always raises on failure. That left the remediation message unreachable whenever `sudo -n`
    failed for real (e.g. "sudo: interactive authentication is required").
    """
    mock_shutil_rmtree.side_effect = PermissionError
    mock_echo.confirm.return_value = True
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        1, ["sudo", "-n", "rm", "-rf"], stderr="sudo: interactive authentication is required\n"
    )

    with pytest.raises(typer.Exit):
        rmtree(directory)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        f"sudo rm -rf failed. Remove manually: sudo rm -rf {directory.as_posix()}"
    )


@mock.patch("deepfellow.common.system.run")
@mock.patch("deepfellow.common.system.echo")
@mock.patch("deepfellow.common.system.shutil.rmtree")
def test_rmtree_permission_error_user_declines_sudo_raises_exit(
    mock_shutil_rmtree: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_shutil_rmtree.side_effect = PermissionError
    mock_echo.confirm.return_value = False

    with pytest.raises(typer.Exit):
        rmtree(directory)

    assert mock_run.call_count == 0
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(f"Remove manually: sudo rm -rf {directory.as_posix()}")
