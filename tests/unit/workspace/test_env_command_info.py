# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.workspace.env_command.info import ENV_METADATA, info


def _printed(mock_echo: Mock) -> str:
    return str(mock_echo.info.call_args.args[0])


@mock.patch("deepfellow.common.env.echo")
def test_env_info_exits_without_installation(mock_echo: Mock, tmp_path: Path):
    with pytest.raises(typer.Exit):
        info(directory=tmp_path / "missing", secret=False, doc=False)

    assert mock_echo.info.call_count == 0


@mock.patch("deepfellow.common.env.echo")
def test_env_info_hides_secrets_by_default(mock_echo: Mock, workspace_dir: Path):
    info(directory=workspace_dir, secret=False, doc=False)

    printed = _printed(mock_echo)
    assert "app-secret-value" not in printed
    assert "server-api-key" not in printed
    assert "APP_SECRET[/]: [dim]*****[/dim]" in printed


@mock.patch("deepfellow.common.env.echo")
def test_env_info_shows_secrets_with_secret_flag(mock_echo: Mock, workspace_dir: Path):
    info(directory=workspace_dir, secret=True, doc=False)

    assert "app-secret-value" in _printed(mock_echo)


@mock.patch("deepfellow.common.env.echo")
def test_env_info_shows_dollar_unescaped(mock_echo: Mock, workspace_dir: Path):
    info(directory=workspace_dir, secret=True, doc=False)

    printed = _printed(mock_echo)
    assert "mcp-Pa$word#1-1234567890" in printed
    assert "Pa$$word" not in printed


@mock.patch("deepfellow.common.env.echo")
def test_env_info_keeps_keys_without_df_prefix(mock_echo: Mock, workspace_dir: Path):
    info(directory=workspace_dir, secret=False, doc=False)

    printed = _printed(mock_echo)
    assert "[cyan bold]SMALL_MODEL[/]" in printed
    assert "[cyan bold]DF_SERVER_URL[/]" in printed
    assert "DF_SMALL_MODEL" not in printed


@mock.patch("deepfellow.common.env.echo")
def test_env_info_shows_empty_value_as_empty_quotes(mock_echo: Mock, workspace_dir: Path):
    info(directory=workspace_dir, secret=False, doc=False)

    assert 'DF_WORKSPACE_BIND_ADDRESS[/]: [dim]""[/dim]' in _printed(mock_echo)


@mock.patch("deepfellow.common.env.echo")
def test_env_info_doc_lists_known_keys(mock_echo: Mock, workspace_dir: Path):
    info(directory=workspace_dir, secret=False, doc=True)

    printed = _printed(mock_echo)
    for key, meta in ENV_METADATA.items():
        assert f"[cyan bold]{key}[/]" in printed
        assert meta.description in printed


@pytest.mark.parametrize(
    "key",
    [
        "DF_SERVER_API_KEY",
        "APP_SECRET",
        "MCP_AUTH_TOKEN",
        "BOOTSTRAP_ADMIN_PASSWORD",
        "SMTP_PASSWORD",
        "DF_WORKSPACE_MONGO_PASSWORD",
        "DF_WORKSPACE_MONGO_KEY",
        "MONGO_DB_URL",
        "REDIS_URL",
    ],
)
def test_env_metadata_marks_secret_as_sensitive(key: str):
    result = ENV_METADATA[key].sensitive

    assert result is True


@mock.patch("deepfellow.workspace.utils.install.echo")
@mock.patch("deepfellow.common.env.echo")
def test_env_info_without_env_file_exits(mock_echo: Mock, mock_install_echo: Mock, tmp_path: Path):
    (tmp_path / "compose.yaml").write_text("services: {}")

    with pytest.raises(typer.Exit) as exc_info:
        info(directory=tmp_path, secret=False, doc=False)

    assert exc_info.value.exit_code == 1
    assert mock_echo.info.call_count == 0
