# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.cli.uninstall import (
    _build_uninstall_command,
    _down_docker_compose,
    _get_uninstall_command,
    _resolve_prune,
    uninstall,
)
from deepfellow.common.state import state

_UV_UNINSTALL_CMD = ["uv", "tool", "uninstall", "deepfellow-cli"]


@mock.patch("deepfellow.cli.uninstall.run", return_value="deepfellow-cli 0.4.0")
@mock.patch("deepfellow.cli.uninstall.is_command_available", return_value=True)
def test_build_uninstall_command_uses_uv_tool_when_package_listed(mock_is_available: Mock, mock_run: Mock) -> None:
    cmd = _build_uninstall_command()

    assert cmd == ["uv", "tool", "uninstall", "deepfellow-cli"]


@mock.patch("deepfellow.cli.uninstall.run")
@mock.patch("deepfellow.cli.uninstall.is_command_available", side_effect=[True, True])
def test_build_uninstall_command_uses_pipx_when_package_listed(mock_is_available: Mock, mock_run: Mock) -> None:
    mock_run.side_effect = [
        "",  # uv tool list — package not found
        "   deepfellow-cli 0.4.0",  # pipx list — package found
    ]

    cmd = _build_uninstall_command()

    assert cmd == ["pipx", "uninstall", "deepfellow-cli"]


@mock.patch("deepfellow.cli.uninstall.run")
@mock.patch("deepfellow.cli.uninstall.is_command_available", side_effect=[True, True, True])
def test_build_uninstall_command_falls_back_to_pip3_when_uv_and_pipx_list_empty(
    mock_is_available: Mock, mock_run: Mock
) -> None:
    mock_run.side_effect = [
        "",  # uv tool list — package not found
        "",  # pipx list — package not found
    ]

    cmd = _build_uninstall_command()

    assert cmd == ["pip3", "uninstall", "deepfellow-cli", "-y"]


@mock.patch("deepfellow.cli.uninstall.run")
@mock.patch("deepfellow.cli.uninstall.is_command_available", side_effect=[True, True, False, True])
def test_build_uninstall_command_falls_back_to_pip_when_pip3_unavailable(
    mock_is_available: Mock, mock_run: Mock
) -> None:
    mock_run.side_effect = [
        "",  # uv tool list — package not found
        "",  # pipx list — package not found
    ]

    cmd = _build_uninstall_command()

    assert cmd == ["pip", "uninstall", "deepfellow-cli", "-y"]


@mock.patch("deepfellow.cli.uninstall.run", return_value="")
@mock.patch("deepfellow.cli.uninstall.is_command_available", return_value=False)
def test_build_uninstall_command_returns_none_when_no_package_manager(mock_is_available: Mock, mock_run: Mock) -> None:
    cmd = _build_uninstall_command()

    assert cmd is None


@mock.patch("deepfellow.cli.uninstall._build_uninstall_command")
def test_get_uninstall_command_reads_from_config_file(mock_build: Mock, tmp_path: Path) -> None:
    config_file = tmp_path / "config"
    config_file.write_text("DF_UNINSTALL_COMMAND=uv tool uninstall deepfellow-cli\n")
    state.cli_config_file = config_file

    cmd = _get_uninstall_command()

    assert cmd == ["uv", "tool", "uninstall", "deepfellow-cli"]
    assert mock_build.call_count == 0

    state.reset()


@mock.patch("deepfellow.cli.uninstall._build_uninstall_command", return_value=["pipx", "uninstall", "deepfellow-cli"])
def test_get_uninstall_command_falls_back_to_detection_when_config_missing(mock_build: Mock, tmp_path: Path) -> None:
    state.cli_config_file = tmp_path / "nonexistent_config"

    cmd = _get_uninstall_command()

    assert cmd == ["pipx", "uninstall", "deepfellow-cli"]
    assert mock_build.call_count == 1

    state.reset()


@mock.patch("deepfellow.cli.uninstall._build_uninstall_command", return_value=_UV_UNINSTALL_CMD)
def test_get_uninstall_command_falls_back_when_config_has_no_uninstall_key(mock_build: Mock, tmp_path: Path) -> None:
    config_file = tmp_path / "config"
    config_file.write_text("DF_SERVER_URL=http://localhost:8000\n")
    state.cli_config_file = config_file

    cmd = _get_uninstall_command()

    assert cmd == ["uv", "tool", "uninstall", "deepfellow-cli"]
    assert mock_build.call_count == 1

    state.reset()


@mock.patch("deepfellow.cli.uninstall.echo")
@mock.patch("deepfellow.cli.uninstall._get_uninstall_command", return_value=None)
def test_uninstall_exits_with_error_when_no_package_manager(mock_get: Mock, mock_echo: Mock) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        uninstall(prune=False)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.cli.uninstall.echo")
@mock.patch("deepfellow.cli.uninstall.run", return_value="ok")
@mock.patch("deepfellow.cli.uninstall._get_uninstall_command", return_value=_UV_UNINSTALL_CMD)
def test_uninstall_runs_detected_command_with_yes_flag(mock_get: Mock, mock_run: Mock, mock_echo: Mock) -> None:
    state.yes = True

    uninstall(prune=False)

    assert mock_run.call_count == 1
    assert mock_run.call_args == (
        (["uv", "tool", "uninstall", "deepfellow-cli"],),
        {},
    )
    assert mock_echo.success.call_count == 1

    state.reset()


@mock.patch("deepfellow.cli.uninstall.echo")
@mock.patch("deepfellow.cli.uninstall.run", side_effect=typer.Exit(1))
@mock.patch("deepfellow.cli.uninstall._get_uninstall_command", return_value=_UV_UNINSTALL_CMD)
def test_uninstall_exits_when_run_fails(mock_get: Mock, mock_run: Mock, mock_echo: Mock) -> None:
    state.yes = True

    with pytest.raises(typer.Exit) as exc_info:
        uninstall(prune=False)

    assert exc_info.value.exit_code == 1
    assert mock_echo.success.call_count == 0

    state.reset()


@mock.patch("deepfellow.cli.uninstall.DF_DEEPFELLOW_DIRECTORY")
@mock.patch("deepfellow.cli.uninstall.DF_SERVER_DIRECTORY")
@mock.patch("deepfellow.cli.uninstall.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.cli.uninstall.rmtree")
@mock.patch("deepfellow.cli.uninstall._down_docker_compose")
@mock.patch("deepfellow.cli.uninstall.echo")
@mock.patch("deepfellow.cli.uninstall.run", return_value="ok")
@mock.patch("deepfellow.cli.uninstall._get_uninstall_command", return_value=_UV_UNINSTALL_CMD)
def test_uninstall_prune_removes_data_when_prune_flag_set(
    mock_get: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_down: Mock,
    mock_rmtree: Mock,
    mock_infra_dir: Mock,
    mock_server_dir: Mock,
    mock_deepfellow_dir: Mock,
) -> None:
    mock_infra_dir.exists.return_value = True
    mock_server_dir.exists.return_value = True
    mock_deepfellow_dir.exists.return_value = True
    state.yes = True

    uninstall(prune=True)

    assert mock_down.call_count == 2
    assert mock_rmtree.call_count == 1
    assert mock_rmtree.call_args == mock.call(mock_deepfellow_dir)

    state.reset()


@mock.patch("deepfellow.cli.uninstall.DF_DEEPFELLOW_DIRECTORY")
@mock.patch("deepfellow.cli.uninstall.DF_SERVER_DIRECTORY")
@mock.patch("deepfellow.cli.uninstall.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.cli.uninstall.rmtree")
@mock.patch("deepfellow.cli.uninstall._down_docker_compose")
@mock.patch("deepfellow.cli.uninstall.echo")
@mock.patch("deepfellow.cli.uninstall.run", return_value="ok")
@mock.patch("deepfellow.cli.uninstall._get_uninstall_command", return_value=_UV_UNINSTALL_CMD)
def test_uninstall_prune_skips_missing_directories(
    mock_get: Mock,
    mock_run: Mock,
    mock_echo: Mock,
    mock_down: Mock,
    mock_rmtree: Mock,
    mock_infra_dir: Mock,
    mock_server_dir: Mock,
    mock_deepfellow_dir: Mock,
) -> None:
    mock_infra_dir.exists.return_value = False
    mock_server_dir.exists.return_value = False
    mock_deepfellow_dir.exists.return_value = False
    state.yes = True

    uninstall(prune=True)

    assert mock_down.call_count == 0
    assert mock_rmtree.call_count == 0

    state.reset()


@mock.patch("deepfellow.cli.uninstall.echo")
@mock.patch("deepfellow.cli.uninstall._get_uninstall_command", return_value=_UV_UNINSTALL_CMD)
def test_uninstall_exits_when_user_declines_confirmation(mock_get: Mock, mock_echo: Mock) -> None:
    mock_echo.confirm.return_value = False
    state.yes = False

    with pytest.raises(typer.Exit) as exc_info:
        uninstall(prune=False)

    assert exc_info.value.exit_code == 0

    state.reset()


@mock.patch("deepfellow.cli.uninstall._build_uninstall_command", return_value=_UV_UNINSTALL_CMD)
@mock.patch("deepfellow.cli.uninstall.echo")
def test_get_uninstall_command_falls_back_when_config_has_malformed_command(
    mock_echo: Mock, mock_build: Mock, tmp_path: Path
) -> None:
    config_file = tmp_path / "config"
    config_file.write_text('DF_UNINSTALL_COMMAND=uv "unmatched\n')
    state.cli_config_file = config_file

    cmd = _get_uninstall_command()

    assert cmd == _UV_UNINSTALL_CMD
    assert mock_echo.warning.call_count == 1
    assert mock_build.call_count == 1

    state.reset()


@mock.patch("deepfellow.cli.uninstall.run", return_value="ok")
@mock.patch("deepfellow.cli.uninstall.is_command_available", return_value=True)
def test_down_docker_compose_runs_compose_down_when_docker_available(
    mock_is_available: Mock, mock_run: Mock, tmp_path: Path
) -> None:
    _down_docker_compose(tmp_path)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "down", "-v"], tmp_path, quiet=True)


@mock.patch("deepfellow.cli.uninstall.run")
@mock.patch("deepfellow.cli.uninstall.is_command_available", return_value=False)
@mock.patch("deepfellow.cli.uninstall.echo")
def test_down_docker_compose_warns_and_skips_when_docker_unavailable(
    mock_echo: Mock, mock_is_available: Mock, mock_run: Mock, tmp_path: Path
) -> None:
    _down_docker_compose(tmp_path)

    assert mock_run.call_count == 0
    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.cli.uninstall.run", side_effect=typer.Exit(1))
@mock.patch("deepfellow.cli.uninstall.is_command_available", return_value=True)
@mock.patch("deepfellow.cli.uninstall.echo")
def test_down_docker_compose_warns_when_compose_down_fails(
    mock_echo: Mock, mock_is_available: Mock, mock_run: Mock, tmp_path: Path
) -> None:
    _down_docker_compose(tmp_path)

    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.cli.uninstall.echo")
def test_resolve_prune_exits_when_user_declines_safety_confirmation(mock_echo: Mock) -> None:
    mock_echo.confirm.side_effect = [True, False]  # accept first, decline safety check

    with pytest.raises(typer.Exit) as exc_info:
        _resolve_prune(prune=False, yes=False)

    assert exc_info.value.exit_code == 0
    assert mock_echo.confirm.call_count == 2


@mock.patch("deepfellow.cli.uninstall.echo")
def test_resolve_prune_returns_true_when_user_confirms_both_prompts(mock_echo: Mock) -> None:
    mock_echo.confirm.side_effect = [True, True]  # accept first, accept safety check

    result = _resolve_prune(prune=False, yes=False)

    assert result is True
    assert mock_echo.confirm.call_count == 2
