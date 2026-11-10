# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.defaults import WORKSPACE_MONGO_VOLUME
from deepfellow.workspace.info import info
from deepfellow.workspace.utils.install import write_stack

EXTERNAL_MONGO_URL = "mongodb://user:mongo-pw@db.example.com:27017/?replicaSet=rs0"
EXTERNAL_REDIS_URL = "redis://:redis-pw@cache.example.com:6379"


def _printed(mock_echo: Mock) -> str:
    return str(mock_echo.info.call_args.args[0])


@mock.patch("deepfellow.workspace.info.echo")
def test_info_exits_without_installation(mock_echo: Mock, tmp_path: Path):
    with pytest.raises(typer.Exit):
        info(directory=tmp_path / "missing", secret=False)

    assert mock_echo.info.call_count == 0


@mock.patch("deepfellow.workspace.info.workspace_running", return_value=True)
@mock.patch("deepfellow.workspace.info.echo")
def test_info_shows_version_from_image_tag(mock_echo: Mock, mock_is_running: Mock, workspace_dir: Path):
    info(directory=workspace_dir, secret=False)

    printed = _printed(mock_echo)
    assert "Version[/]: [yellow]0.7.0[/yellow]" in printed
    assert "Running[/]: [yellow]yes[/yellow]" in printed
    assert "Local address[/]: [yellow]http://localhost:3000[/yellow]" in printed


@mock.patch("deepfellow.workspace.info.workspace_running", return_value=False)
@mock.patch("deepfellow.workspace.info.echo")
def test_info_local_services_and_email_off(mock_echo: Mock, mock_is_running: Mock, workspace_dir: Path):
    info(directory=workspace_dir, secret=False)

    printed = _printed(mock_echo)
    assert "Mongo[/]: [yellow]local[/yellow]" in printed
    assert "Redis[/]: [yellow]local[/yellow]" in printed
    assert "E-mail[/]: [yellow]off[/yellow]" in printed
    assert "Running[/]: [yellow]no[/yellow]" in printed


@mock.patch("deepfellow.workspace.info.workspace_running", return_value=True)
@mock.patch("deepfellow.workspace.info.echo")
def test_info_email_on_shows_host_port_and_sender(
    mock_echo: Mock, mock_is_running: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    smtp = {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_USERNAME": "user",
        "SMTP_PASSWORD": "smtp-secret",
        "EMAIL_FROM_ADDRESS": "ws@example.com",
    }
    write_stack(tmp_path, {**installed_env, **smtp})

    info(directory=tmp_path, secret=True)

    printed = _printed(mock_echo)
    assert "(smtp.example.com:587, from ws@example.com)" in printed
    assert "smtp-secret" not in printed


@mock.patch("deepfellow.workspace.info.workspace_running", return_value=True)
@mock.patch("deepfellow.workspace.info.echo")
def test_info_external_mongo_and_redis_hidden_by_default(
    mock_echo: Mock, mock_is_running: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    write_stack(tmp_path, {**installed_env, "MONGO_DB_URL": EXTERNAL_MONGO_URL, "REDIS_URL": EXTERNAL_REDIS_URL})

    info(directory=tmp_path, secret=False)

    printed = _printed(mock_echo)
    assert "Mongo[/]: [yellow]external[/yellow] [dim]*****[/dim]" in printed
    assert "Redis[/]: [yellow]external[/yellow] [dim]*****[/dim]" in printed
    assert "mongo-pw" not in printed
    assert "redis-pw" not in printed


@mock.patch("deepfellow.workspace.info.workspace_running", return_value=True)
@mock.patch("deepfellow.workspace.info.echo")
def test_info_hides_api_key_and_mcp_token_by_default(mock_echo: Mock, mock_is_running: Mock, workspace_dir: Path):
    info(directory=workspace_dir, secret=False)

    printed = _printed(mock_echo)
    assert "API key[/]: [dim]*****[/dim]" in printed
    assert "MCP token[/]: [dim]*****[/dim]" in printed
    assert "server-api-key" not in printed


@mock.patch("deepfellow.workspace.info.workspace_running", return_value=True)
@mock.patch("deepfellow.workspace.info.echo")
def test_info_secret_reveals_api_key_and_mcp_token(mock_echo: Mock, mock_is_running: Mock, workspace_dir: Path):
    info(directory=workspace_dir, secret=True)

    printed = _printed(mock_echo)
    assert "server-api-key" in printed
    assert "mcp-Pa$word#1-1234567890" in printed


@pytest.mark.parametrize("secret", [False, True])
@mock.patch("deepfellow.workspace.info.workspace_running", return_value=True)
@mock.patch("deepfellow.workspace.info.echo")
def test_info_never_shows_app_secret_or_mongo_password(
    mock_echo: Mock, mock_is_running: Mock, secret: bool, workspace_dir: Path
):
    info(directory=workspace_dir, secret=secret)

    printed = _printed(mock_echo)
    for value in ("app-secret-value", "mongo-password", "mongo-keyfile"):
        assert value not in printed


@mock.patch("deepfellow.workspace.info.workspace_running", return_value=None)
@mock.patch("deepfellow.workspace.info.echo")
def test_info_running_state_unknown_without_docker(mock_echo: Mock, mock_is_running: Mock, workspace_dir: Path):
    info(directory=workspace_dir, secret=False)

    assert "Running[/]: [yellow]unknown[/yellow]" in _printed(mock_echo)


@mock.patch("deepfellow.workspace.info.workspace_running", return_value=True)
@mock.patch("deepfellow.workspace.info.echo")
def test_info_reminds_to_remove_admin_password(
    mock_echo: Mock, mock_is_running: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    admin = {
        "BOOTSTRAP_ADMIN_NAME": "Admin",
        "BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
        "BOOTSTRAP_ADMIN_PASSWORD": "Admin-pass-123",
    }
    write_stack(tmp_path, {**installed_env, **admin})

    info(directory=tmp_path, secret=True)

    assert "BOOTSTRAP_ADMIN_*" in str(mock_echo.warning.call_args.args[0])
    assert "Admin-pass-123" not in _printed(mock_echo)


@mock.patch("deepfellow.workspace.info.workspace_running", return_value=True)
@mock.patch("deepfellow.workspace.info.echo")
def test_info_without_admin_password_does_not_warn(mock_echo: Mock, mock_is_running: Mock, workspace_dir: Path):
    info(directory=workspace_dir, secret=False)

    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.workspace.info.workspace_running", return_value=True)
@mock.patch("deepfellow.workspace.info.echo")
def test_info_shows_missing_secret_as_not_set(
    mock_echo: Mock, mock_is_running: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    write_stack(tmp_path, {**installed_env, "MCP_AUTH_TOKEN": ""})

    info(directory=tmp_path, secret=False)

    assert "MCP token[/]: [dim]not set[/dim]" in _printed(mock_echo)


@mock.patch("deepfellow.workspace.info.workspace_running", return_value=True)
@mock.patch("deepfellow.workspace.info.echo")
def test_info_secret_reveals_external_mongo_and_redis_urls(
    mock_echo: Mock, mock_is_running: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    write_stack(tmp_path, {**installed_env, "MONGO_DB_URL": EXTERNAL_MONGO_URL, "REDIS_URL": EXTERNAL_REDIS_URL})

    info(directory=tmp_path, secret=True)

    printed = _printed(mock_echo)
    assert EXTERNAL_MONGO_URL in printed
    assert EXTERNAL_REDIS_URL in printed


@mock.patch("deepfellow.workspace.info.workspace_running", return_value=True)
@mock.patch("deepfellow.workspace.info.echo")
def test_info_local_mongo_names_its_docker_volume(mock_echo: Mock, mock_is_running: Mock, workspace_dir: Path):
    info(directory=workspace_dir, secret=False)

    assert f"Mongo[/]: [yellow]local[/yellow] (Docker volume of '{WORKSPACE_MONGO_VOLUME}')" in _printed(mock_echo)


@mock.patch("deepfellow.workspace.utils.install.echo")
@mock.patch("deepfellow.workspace.info.echo")
def test_info_without_env_file_exits(mock_echo: Mock, mock_install_echo: Mock, tmp_path: Path):
    (tmp_path / "compose.yaml").write_text("services: {}")

    with pytest.raises(typer.Exit) as exc_info:
        info(directory=tmp_path, secret=False)

    assert exc_info.value.exit_code == 1
    assert mock_echo.info.call_count == 0
    assert "workspace install" in str(mock_install_echo.error.call_args.args[0])
