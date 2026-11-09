# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from typer.testing import CliRunner

from deepfellow.main import app

runner = CliRunner()


def test_workspace_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["workspace", "--help"])

    assert result.exit_code == 0
    assert "install" in result.output
    for name in ("uninstall", "start", "stop", "restart", "status", "logs"):
        assert name in result.output


def test_workspace_install_rejects_smtp_port_out_of_range() -> None:
    result = runner.invoke(app, ["workspace", "install", "--smtp-port", "0"])

    assert result.exit_code == 2


def test_workspace_install_rejects_short_mcp_auth_token() -> None:
    result = runner.invoke(app, ["workspace", "install", "--mcp-auth-token", "short"])

    assert result.exit_code == 2
