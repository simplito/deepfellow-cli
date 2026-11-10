# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from typer.testing import CliRunner

from deepfellow.main import app

runner = CliRunner()


def test_workspace_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["workspace", "--help"])

    assert result.exit_code == 0
    assert "install" in result.output
    for name in ("uninstall", "start", "stop", "restart", "status", "logs", "update", "info", "env"):
        assert name in result.output


def test_workspace_env_help_lists_info_and_set():
    result = runner.invoke(app, ["workspace", "env", "--help"])

    assert result.exit_code == 0
    assert "info" in result.output
    assert "set" in result.output


def test_workspace_update_rejects_image_and_tag_together():
    result = runner.invoke(app, ["workspace", "update", "--image", "img:1", "--tag", "v1.0.0"])

    assert result.exit_code == 2


def test_workspace_install_rejects_smtp_port_out_of_range() -> None:
    result = runner.invoke(app, ["workspace", "install", "--smtp-port", "0"])

    assert result.exit_code == 2


def test_workspace_install_rejects_short_mcp_auth_token() -> None:
    result = runner.invoke(app, ["workspace", "install", "--mcp-auth-token", "short"])

    assert result.exit_code == 2


def test_workspace_install_rejects_invalid_trusted_origin() -> None:
    result = runner.invoke(app, ["workspace", "install", "--trusted-origins", "https://a.example.com,not-an-origin"])

    assert result.exit_code == 2
    assert "not-an-origin" in result.output
