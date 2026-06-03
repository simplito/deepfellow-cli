# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.cli.update import _build_update_command, update


@mock.patch("deepfellow.cli.update.run", return_value="deepfellow-cli 0.4.0")
@mock.patch("deepfellow.cli.update.is_command_available", return_value=True)
def test_build_update_command_uses_uv_tool_when_package_listed(mock_is_available: Mock, mock_run: Mock) -> None:
    cmd = _build_update_command()

    assert cmd == ["uv", "tool", "upgrade", "deepfellow-cli"]


@mock.patch("deepfellow.cli.update.run", return_value="")
@mock.patch("deepfellow.cli.update.is_command_available", side_effect=[True, True])
def test_build_update_command_uses_pipx_when_package_listed(mock_is_available: Mock, mock_run: Mock) -> None:
    mock_run.side_effect = [
        "",  # uv tool list — package not found
        "   deepfellow-cli 0.4.0",  # pipx list — package found
    ]

    cmd = _build_update_command()

    assert cmd == ["pipx", "upgrade", "deepfellow-cli"]


@mock.patch("deepfellow.cli.update.run")
@mock.patch("deepfellow.cli.update.is_command_available", side_effect=[True, True])
def test_build_update_command_returns_none_when_pipx_list_does_not_contain_package(
    mock_is_available: Mock, mock_run: Mock
) -> None:
    mock_run.side_effect = [
        "",  # uv tool list — package not found
        "",  # pipx list — package not found
    ]

    cmd = _build_update_command()

    assert cmd is None


@mock.patch("deepfellow.cli.update.run", return_value="")
@mock.patch("deepfellow.cli.update.is_command_available", return_value=False)
def test_build_update_command_returns_none_when_no_package_manager_detected(
    mock_is_available: Mock, mock_run: Mock
) -> None:
    cmd = _build_update_command()

    assert cmd is None


@mock.patch("deepfellow.cli.update.echo")
@mock.patch("deepfellow.cli.update.run", return_value="ok")
@mock.patch("deepfellow.cli.update._build_update_command")
def test_update_runs_detected_command(mock_build: Mock, mock_run: Mock, mock_echo: Mock) -> None:
    mock_build.return_value = ["uv", "tool", "upgrade", "deepfellow-cli"]

    update()

    assert mock_run.call_count == 1
    assert mock_run.call_args == (
        (["uv", "tool", "upgrade", "deepfellow-cli"],),
        {},
    )


@mock.patch("deepfellow.cli.update.echo")
@mock.patch("deepfellow.cli.update.run", return_value="ok")
@mock.patch("deepfellow.cli.update._build_update_command")
def test_update_prints_success(mock_build: Mock, mock_run: Mock, mock_echo: Mock) -> None:
    mock_build.return_value = ["uv", "tool", "upgrade", "deepfellow-cli"]

    update()

    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.cli.update.echo")
@mock.patch("deepfellow.cli.update._build_update_command", return_value=None)
def test_update_exits_with_error_when_no_package_manager_detected(mock_build: Mock, mock_echo: Mock) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        update()

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.cli.update.echo")
@mock.patch("deepfellow.cli.update.run", return_value=None)
@mock.patch("deepfellow.cli.update._build_update_command")
def test_update_exits_when_run_fails(mock_build: Mock, mock_run: Mock, mock_echo: Mock) -> None:
    mock_build.return_value = ["uv", "tool", "upgrade", "deepfellow-cli"]

    with pytest.raises(typer.Exit) as exc_info:
        update()

    assert exc_info.value.exit_code == 1
    assert mock_echo.success.call_count == 0
