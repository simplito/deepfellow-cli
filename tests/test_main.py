# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import runpy
import sys
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.state import state
from deepfellow.main import main, print_name, version


@mock.patch("deepfellow.main.validate_system")
@mock.patch("deepfellow.main.print_version")
def test_main_shows_version_and_exits_when_version_flag_set(
    mock_print_version: Mock,
    mock_validate_system: Mock,
    tmp_path: Path,
) -> None:
    ctx = Mock(spec=typer.Context)

    with pytest.raises(typer.Exit) as exc_info:
        main(
            ctx,
            config=tmp_path / "config",
            secrets=tmp_path / "secrets",
            debug=False,
            yes=False,
            non_interactive=False,
            _version=True,
        )

    assert exc_info.value.exit_code == 0
    assert mock_print_version.call_count == 1
    assert mock_validate_system.call_count == 0


@mock.patch("deepfellow.main.validate_system")
@mock.patch("deepfellow.main.print_name")
def test_main_prints_name_and_exits_when_no_subcommand_invoked(
    mock_print_name: Mock,
    mock_validate_system: Mock,
    tmp_path: Path,
) -> None:
    ctx = Mock(spec=typer.Context)
    ctx.invoked_subcommand = None

    with pytest.raises(typer.Exit) as exc_info:
        main(
            ctx,
            config=tmp_path / "config",
            secrets=tmp_path / "secrets",
            debug=False,
            yes=False,
            non_interactive=False,
            _version=False,
        )

    assert exc_info.value.exit_code == 0
    assert mock_print_name.call_count == 1
    assert mock_validate_system.call_count == 0


@mock.patch("deepfellow.main.validate_system")
@mock.patch("deepfellow.main.save_env_file")
@mock.patch("deepfellow.main.env_to_dict", return_value={"foo": "bar"})
@mock.patch("deepfellow.main.read_env_file", return_value={"DF_FOO": "bar"})
def test_main_loads_existing_config_file(
    mock_read_env_file: Mock,
    mock_env_to_dict: Mock,
    mock_save_env_file: Mock,
    mock_validate_system: Mock,
    tmp_path: Path,
) -> None:
    ctx = Mock(spec=typer.Context)
    ctx.invoked_subcommand = "version"
    config = tmp_path / "config"
    config.write_text("DF_FOO=bar\n")
    secrets = tmp_path / "secrets"

    main(
        ctx,
        config=config,
        secrets=secrets,
        debug=True,
        yes=True,
        non_interactive=True,
        _version=False,
    )

    assert mock_read_env_file.call_count == 1
    assert mock_read_env_file.call_args == mock.call(config)
    assert mock_env_to_dict.call_args == mock.call({"DF_FOO": "bar"})
    assert mock_save_env_file.call_count == 0
    assert mock_validate_system.call_count == 1
    assert state.debug is True
    assert state.yes is True
    assert state.non_interactive is True
    assert state.cli_config == {"foo": "bar"}
    assert state.cli_config_file == config
    assert state.cli_secrets_file == secrets


@mock.patch("deepfellow.main.validate_system")
@mock.patch("deepfellow.main.save_env_file")
@mock.patch("deepfellow.main.read_env_file")
def test_main_saves_new_config_file_when_missing(
    mock_read_env_file: Mock,
    mock_save_env_file: Mock,
    mock_validate_system: Mock,
    tmp_path: Path,
) -> None:
    ctx = Mock(spec=typer.Context)
    ctx.invoked_subcommand = "version"
    config = tmp_path / "config"
    secrets = tmp_path / "secrets"

    main(
        ctx,
        config=config,
        secrets=secrets,
        debug=False,
        yes=False,
        non_interactive=False,
        _version=False,
    )

    assert mock_save_env_file.call_count == 1
    assert mock_save_env_file.call_args == mock.call(config, {}, docker_note=False)
    assert mock_read_env_file.call_count == 0
    assert mock_validate_system.call_count == 1
    assert state.cli_config == {}


@mock.patch("deepfellow.main.echo")
@mock.patch("deepfellow.main.get_version", return_value="1.2.3")
def test_version_prints_installed_version(mock_get_version: Mock, mock_echo: Mock) -> None:
    version()

    assert mock_get_version.call_count == 1
    assert mock_get_version.call_args == mock.call("deepfellow-cli")
    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == mock.call("1.2.3")
    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.main.echo")
@mock.patch("deepfellow.main.get_version", side_effect=PackageNotFoundError)
def test_version_prints_error_when_package_not_found(mock_get_version: Mock, mock_echo: Mock) -> None:
    version()

    assert mock_get_version.call_count == 1
    assert mock_echo.error.call_count == 1
    assert mock_echo.success.call_count == 0


def test_print_name_prints_ascii_art(capsys: pytest.CaptureFixture[str]) -> None:
    print_name()

    captured = capsys.readouterr()
    assert "VERSION:" in captured.out
    assert "`deepfellow --help` for help with commands." in captured.out


def test_main_module_invokes_app_when_run_as_script(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["deepfellow"])
    monkeypatch.delitem(sys.modules, "deepfellow.main")

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("deepfellow.main", run_name="__main__")

    assert exc_info.value.code == 0
