# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer
from typer.testing import CliRunner

from deepfellow.common.defaults import (
    MONGO_IMAGE,
    WORKSPACE_MONGO_SERVICE,
    WORKSPACE_REDIS_IMAGE,
    WORKSPACE_REDIS_SERVICE,
)
from deepfellow.common.docker import load_compose_file, save_compose_file
from deepfellow.common.exceptions import InstallError
from deepfellow.main import app
from deepfellow.workspace.env_command.set import set as env_set
from deepfellow.workspace.utils.install import current_service_images, read_existing_env, write_stack

runner = CliRunner()


def _set(directory: Path, name: str, value: str = "", no_restart: bool = False) -> None:
    env_set(directory=directory, env_name=name, env_value=value, no_restart=no_restart)


def _compose_services(directory: Path) -> dict[str, dict[str, object]]:
    return load_compose_file(directory / "compose.yaml")["services"]


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_writes_app_key_without_df_prefix(mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path):
    result = runner.invoke(app, ["workspace", "env", "set", "--directory", str(workspace_dir), "small_model", "llama3"])

    assert result.exit_code == 0
    env = read_existing_env(workspace_dir)
    assert env["SMALL_MODEL"] == "llama3"
    assert "DF_SMALL_MODEL" not in env


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_keeps_other_values_with_dollar(mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path):
    before = read_existing_env(workspace_dir)

    _set(workspace_dir, "SMALL_MODEL", "llama3")

    after = read_existing_env(workspace_dir)
    assert after["MCP_AUTH_TOKEN"] == "mcp-Pa$word#1-1234567890"
    assert {key: value for key, value in after.items() if key != "SMALL_MODEL"} == {
        key: value for key, value in before.items() if key != "SMALL_MODEL"
    }


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_empty_value_removes_key(
    mock_echo: Mock, mock_offer_restart: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    write_stack(tmp_path, {**installed_env, "TRUSTED_PROXY_ENABLED": "true"})

    _set(tmp_path, "TRUSTED_PROXY_ENABLED", "")

    env_text = (tmp_path / ".env").read_text()
    assert "TRUSTED_PROXY_ENABLED" not in env_text
    assert 'SMALL_MODEL="small"' in env_text
    assert mock_echo.success.call_args == mock.call(f"TRUSTED_PROXY_ENABLED removed from {tmp_path / '.env'}.")
    assert mock_offer_restart.call_count == 1


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_empty_bind_address_is_kept_as_all_interfaces(
    mock_echo: Mock, mock_offer_restart: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    write_stack(tmp_path, {**installed_env, "DF_WORKSPACE_BIND_ADDRESS": "127.0.0.1"})

    _set(tmp_path, "DF_WORKSPACE_BIND_ADDRESS", "")

    assert 'DF_WORKSPACE_BIND_ADDRESS=""' in (tmp_path / ".env").read_text()
    assert _compose_services(tmp_path)["workspace"]["ports"] == [":3000:3000"]


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_empty_unknown_key_removes_it_without_warning(
    mock_echo: Mock, mock_offer_restart: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    write_stack(tmp_path, {**installed_env, "LOG_LEVEL": "debug"})

    _set(tmp_path, "LOG_LEVEL", "")

    assert "LOG_LEVEL" not in read_existing_env(tmp_path)
    assert mock_echo.warning.call_count == 0


@pytest.mark.parametrize(
    ("name", "value", "error_fragment"),
    [
        ("SMALL_MODEL", "", "Missing required values"),
        ("DF_SERVER_URL", "", "Missing required values"),
        ("DF_SERVER_API_KEY", "", "Missing required values"),
        ("DF_SERVER_ORGANIZATION_ID", "", "Missing required values"),
        ("DF_SERVER_PROJECT_ID", "", "Missing required values"),
        ("FOO=BAR", "x", "not a valid setting name"),
        ("FOO-BAR", "x", "not a valid setting name"),
        ("1ABC", "x", "not a valid setting name"),
        ("", "x", "not a valid setting name"),
        ("APP_SECRET", "new", "signs all users out"),
        ("DF_WORKSPACE_MONGO_PASSWORD", "new", "own copy of the password"),
        ("DF_WORKSPACE_MONGO_KEY", "new", "replica set"),
        ("DF_WORKSPACE_IMAGE", "img:1", "workspace update"),
        ("DF_WORKSPACE_PORT", "", "cannot be removed"),
        ("DF_WORKSPACE_DOCKER_NETWORK", "", "cannot be removed"),
        ("EMAIL_FROM_NAME", "a\nb", "line break"),
        ("DF_WORKSPACE_PORT", "70000", "port"),
        ("DF_WORKSPACE_BIND_ADDRESS", "localhost", "bind address"),
        ("DF_SERVER_URL", "not-a-url", "scheme and domain"),
        ("SMTP_PORT", "0", "port"),
        ("MONGO_DB_URL", "http://db.example.com", "MongoDB URL"),
        ("REDIS_URL", "http://cache.example.com", "Redis URL"),
        ("BOOTSTRAP_ADMIN_EMAIL", "not-an-email", "email"),
        ("BOOTSTRAP_ADMIN_PASSWORD", "weak", "Invalid password"),
        ("TRUSTED_PROXY_ENABLED", "maybe", "true or false"),
        ("PUBLIC_URL", "http://x.example.com/path", "origin"),
        ("EMAIL_FROM_ADDRESS", "not-an-email", "email"),
        ("MCP_AUTH_TOKEN", "short", "16 characters"),
        ("SMTP_SECURE", "yes", "true or false"),
        ("MONGO_DB_NAME", "db", "external MongoDB only"),
    ],
)
@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_refuses_and_leaves_files_unchanged(
    mock_echo: Mock,
    mock_offer_restart: Mock,
    name: str,
    value: str,
    error_fragment: str,
    workspace_dir: Path,
):
    env_before = (workspace_dir / ".env").read_bytes()
    compose_before = (workspace_dir / "compose.yaml").read_bytes()

    with pytest.raises(typer.Exit) as exc_info:
        _set(workspace_dir, name, value)

    assert exc_info.value.exit_code == 1
    assert error_fragment in str(mock_echo.error.call_args.args[0])
    assert (workspace_dir / ".env").read_bytes() == env_before
    assert (workspace_dir / "compose.yaml").read_bytes() == compose_before
    assert mock_offer_restart.call_count == 0


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_regenerates_emptied_mcp_auth_token(mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path):
    _set(workspace_dir, "MCP_AUTH_TOKEN", "")

    token = read_existing_env(workspace_dir)["MCP_AUTH_TOKEN"]
    assert token
    assert token != "mcp-Pa$word#1-1234567890"
    assert any("new MCP_AUTH_TOKEN" in str(call.args[0]) for call in mock_echo.info.call_args_list)


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_normalises_ipv6_bind_address(mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path):
    _set(workspace_dir, "DF_WORKSPACE_BIND_ADDRESS", "::1")

    assert read_existing_env(workspace_dir)["DF_WORKSPACE_BIND_ADDRESS"] == "[::1]"
    assert _compose_services(workspace_dir)["workspace"]["ports"] == ["[::1]:3000:3000"]


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_warns_for_unknown_key(mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path):
    _set(workspace_dir, "LOG_LEVEL", "debug")

    assert read_existing_env(workspace_dir)["LOG_LEVEL"] == "debug"
    assert mock_echo.warning.call_count == 1
    assert "not a known DeepFellow Workspace setting" in str(mock_echo.warning.call_args.args[0])


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_incomplete_smtp_group_writes_and_skips_restart(
    mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path
):
    _set(workspace_dir, "SMTP_HOST", "smtp.example.com")

    assert read_existing_env(workspace_dir)["SMTP_HOST"] == "smtp.example.com"
    warning = str(mock_echo.warning.call_args.args[0])
    assert "SMTP_USERNAME" in warning
    assert "EMAIL_FROM_ADDRESS" in warning
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_port_change_moves_default_public_url(mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path):
    _set(workspace_dir, "DF_WORKSPACE_PORT", "3001")

    assert read_existing_env(workspace_dir)["PUBLIC_URL"] == "http://localhost:3001"
    assert _compose_services(workspace_dir)["workspace"]["ports"] == [":3001:3000"]


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_port_change_keeps_custom_public_url(
    mock_echo: Mock, mock_offer_restart: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    write_stack(tmp_path, {**installed_env, "PUBLIC_URL": "https://workspace.example.com"})

    _set(tmp_path, "DF_WORKSPACE_PORT", "3001")

    assert read_existing_env(tmp_path)["PUBLIC_URL"] == "https://workspace.example.com"


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_explicit_public_url_of_default_form_is_kept(
    mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path
):
    _set(workspace_dir, "PUBLIC_URL", "http://localhost:8080")

    assert read_existing_env(workspace_dir)["PUBLIC_URL"] == "http://localhost:8080"


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_switches_to_external_mongo(mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path):
    _set(workspace_dir, "MONGO_DB_URL", "mongodb://db.example.com:27017/?replicaSet=rs0")

    assert WORKSPACE_MONGO_SERVICE not in _compose_services(workspace_dir)
    warning = str(mock_echo.warning.call_args.args[0])
    assert "not moved" in warning
    assert "Docker volume" in warning


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_switches_back_to_local_mongo_generating_secrets(
    mock_echo: Mock, mock_offer_restart: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    external = {
        key: value
        for key, value in installed_env.items()
        if key not in ("DF_WORKSPACE_MONGO_PASSWORD", "DF_WORKSPACE_MONGO_KEY")
    }
    write_stack(tmp_path, {**external, "MONGO_DB_URL": "mongodb://db.example.com:27017/?replicaSet=rs0"})

    _set(tmp_path, "MONGO_DB_URL", "")

    env = read_existing_env(tmp_path)
    assert "MONGO_DB_URL" not in env
    assert env["DF_WORKSPACE_MONGO_PASSWORD"]
    assert env["DF_WORKSPACE_MONGO_KEY"]
    assert WORKSPACE_MONGO_SERVICE in _compose_services(tmp_path)
    assert "not moved" in str(mock_echo.warning.call_args.args[0])


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_switch_back_to_local_mongo_keeps_existing_secrets(
    mock_echo: Mock, mock_offer_restart: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    write_stack(tmp_path, {**installed_env, "MONGO_DB_URL": "mongodb://db.example.com:27017/?replicaSet=rs0"})

    _set(tmp_path, "MONGO_DB_URL", "")

    env = read_existing_env(tmp_path)
    assert env["DF_WORKSPACE_MONGO_PASSWORD"] == "mongo-password"
    assert env["DF_WORKSPACE_MONGO_KEY"] == "mongo-keyfile"


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_switches_to_external_redis(mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path):
    _set(workspace_dir, "REDIS_URL", "redis://cache.example.com:6379")

    assert WORKSPACE_REDIS_SERVICE not in _compose_services(workspace_dir)
    assert "not moved" in str(mock_echo.warning.call_args.args[0])


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_keeps_mongo_and_redis_images_from_compose(
    mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path
):
    compose = load_compose_file(workspace_dir / "compose.yaml")
    compose["services"][WORKSPACE_MONGO_SERVICE]["image"] = "mongo:8.2.12"
    compose["services"][WORKSPACE_REDIS_SERVICE]["image"] = "redis:7.4"
    save_compose_file(compose, workspace_dir / "compose.yaml")

    _set(workspace_dir, "SMALL_MODEL", "llama3")

    assert current_service_images(workspace_dir) == {
        WORKSPACE_MONGO_SERVICE: "mongo:8.2.12",
        WORKSPACE_REDIS_SERVICE: "redis:7.4",
    }


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_switch_back_to_local_redis_uses_cli_image(
    mock_echo: Mock, mock_offer_restart: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    write_stack(tmp_path, {**installed_env, "REDIS_URL": "redis://cache.example.com:6379"})

    _set(tmp_path, "REDIS_URL", "")

    assert current_service_images(tmp_path) == {
        WORKSPACE_MONGO_SERVICE: MONGO_IMAGE,
        WORKSPACE_REDIS_SERVICE: WORKSPACE_REDIS_IMAGE,
    }


@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_exits_without_installation(mock_echo: Mock, tmp_path: Path):
    with pytest.raises(typer.Exit):
        _set(tmp_path / "missing", "SMALL_MODEL", "llama3")

    assert not (tmp_path / "missing").exists()


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_stores_flag_in_lower_case(mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path):
    _set(workspace_dir, "TRUSTED_PROXY_ENABLED", "TRUE")

    assert read_existing_env(workspace_dir)["TRUSTED_PROXY_ENABLED"] == "true"


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_offers_restart_for_change(mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path):
    _set(workspace_dir, "SMALL_MODEL", "llama3", no_restart=True)

    assert mock_offer_restart.call_count == 1
    assert mock_offer_restart.call_args == mock.call(workspace_dir, "change", True)


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_incomplete_group_does_not_offer_restart(
    mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path
):
    _set(workspace_dir, "BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")

    assert mock_offer_restart.call_count == 0
    warning = str(mock_echo.warning.call_args.args[0])
    assert "BOOTSTRAP_ADMIN_PASSWORD" in warning
    assert "will not start" in warning


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_accepts_mongo_db_name_with_external_mongo(
    mock_echo: Mock, mock_offer_restart: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    write_stack(tmp_path, {**installed_env, "MONGO_DB_URL": "mongodb://db.example.com:27017/?replicaSet=rs0"})

    _set(tmp_path, "MONGO_DB_NAME", "workspace")

    assert read_existing_env(tmp_path)["MONGO_DB_NAME"] == "workspace"


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_unreadable_compose_exits_without_writing(
    mock_echo: Mock, mock_offer_restart: Mock, workspace_dir: Path
):
    (workspace_dir / "compose.yaml").write_text("services: [unclosed")
    env_before = (workspace_dir / ".env").read_bytes()

    with pytest.raises(typer.Exit) as exc_info:
        _set(workspace_dir, "SMALL_MODEL", "llama3")

    assert exc_info.value.exit_code == 1
    assert "Cannot read" in str(mock_echo.error.call_args.args[0])
    assert (workspace_dir / ".env").read_bytes() == env_before
    assert mock_offer_restart.call_count == 0


@mock.patch("deepfellow.workspace.env_command.set.write_stack", side_effect=InstallError("Could not write"))
@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_write_failure_exits(
    mock_echo: Mock, mock_offer_restart: Mock, mock_write_stack: Mock, workspace_dir: Path
):
    with pytest.raises(typer.Exit) as exc_info:
        _set(workspace_dir, "SMALL_MODEL", "llama3")

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_args == mock.call("Could not write")
    assert mock_offer_restart.call_count == 0


@mock.patch("deepfellow.workspace.utils.install.echo")
def test_env_set_without_env_file_exits(mock_echo: Mock, tmp_path: Path):
    (tmp_path / "compose.yaml").write_text("services: {}")

    with pytest.raises(typer.Exit) as exc_info:
        _set(tmp_path, "SMALL_MODEL", "llama3")

    assert exc_info.value.exit_code == 1
    assert "workspace install" in str(mock_echo.error.call_args.args[0])


@mock.patch("deepfellow.workspace.env_command.set.offer_restart")
@mock.patch("deepfellow.workspace.env_command.set.echo")
def test_env_set_empty_public_url_restores_default(
    mock_echo: Mock, mock_offer_restart: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    write_stack(tmp_path, {**installed_env, "PUBLIC_URL": "https://workspace.example.com", "DF_WORKSPACE_PORT": "3005"})

    _set(tmp_path, "PUBLIC_URL", "")

    assert read_existing_env(tmp_path)["PUBLIC_URL"] == "http://localhost:3005"
