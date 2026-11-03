# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from unittest import mock
from unittest.mock import Mock

import typer
from typer.testing import CliRunner

from deepfellow.cli import callback
from deepfellow.main import app


@mock.patch("deepfellow.cli.check_for_update")
def test_callback_runs_update_check_for_uninstall(mock_check_for_update: Mock):
    ctx = Mock(spec=typer.Context)
    ctx.invoked_subcommand = "uninstall"

    callback(ctx)

    assert mock_check_for_update.call_count == 1
    assert mock_check_for_update.call_args == mock.call()


@mock.patch("deepfellow.cli.check_for_update")
def test_callback_skips_update_check_for_update(mock_check_for_update: Mock):
    ctx = Mock(spec=typer.Context)
    ctx.invoked_subcommand = "update"

    callback(ctx)

    assert mock_check_for_update.call_count == 0


@mock.patch("deepfellow.cli.uninstall.resolve_cli_command", return_value=None)
@mock.patch("deepfellow.cli.check_for_update")
@mock.patch("deepfellow.main.check_for_update")
@mock.patch("deepfellow.main.validate_system")
def test_cli_uninstall_runs_update_check_once(
    mock_validate_system: Mock,
    mock_main_check_for_update: Mock,
    mock_cli_check_for_update: Mock,
    mock_resolve_cli_command: Mock,
):
    runner = CliRunner()

    result = runner.invoke(app, ["cli", "uninstall"])

    assert result.exit_code == 1
    assert mock_resolve_cli_command.call_count == 1
    assert mock_main_check_for_update.call_count == 0
    assert mock_cli_check_for_update.call_count == 1


@mock.patch("deepfellow.cli.update.resolve_cli_command", return_value=None)
@mock.patch("deepfellow.cli.check_for_update")
@mock.patch("deepfellow.main.check_for_update")
@mock.patch("deepfellow.main.validate_system")
def test_cli_update_skips_update_check(
    mock_validate_system: Mock,
    mock_main_check_for_update: Mock,
    mock_cli_check_for_update: Mock,
    mock_resolve_cli_command: Mock,
):
    runner = CliRunner()

    result = runner.invoke(app, ["cli", "update"])

    assert result.exit_code == 1
    assert mock_resolve_cli_command.call_count == 1
    assert mock_main_check_for_update.call_count == 0
    assert mock_cli_check_for_update.call_count == 0


def test_cli_help_keeps_group_description():
    runner = CliRunner()

    result = runner.invoke(app, ["cli", "--help"])

    assert result.exit_code == 0
    assert "Manage DeepFellow CLI." in result.output
