# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Tests for the server env set command."""

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import httpx
import pytest
import typer

from deepfellow.common.state import state
from deepfellow.server.env_command.set import _dynamic_field_name, _resolved_env_name, set


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    return tmp_path


@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_restarts_server_when_confirmed(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_dynamic_field_name: Mock,
    mock_is_service_running: Mock,
    directory: Path,
) -> None:
    mock_echo.confirm.return_value = True

    set(directory=directory, env_name="DF_SOME_VAR", env_value="value", df_prefix=True, no_restart=False)

    assert mock_env_set.call_count == 1
    assert mock_echo.confirm.call_count == 1
    assert mock_stop.call_count == 1
    assert mock_stop.call_args == mock.call(directory)
    assert mock_start.call_count == 1
    assert mock_start.call_args == mock.call(directory)
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_skips_restart_when_declined(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_dynamic_field_name: Mock,
    mock_is_service_running: Mock,
    directory: Path,
) -> None:
    mock_echo.confirm.return_value = False

    set(directory=directory, env_name="DF_SOME_VAR", env_value="value", df_prefix=True, no_restart=False)

    assert mock_env_set.call_count == 1
    assert mock_echo.confirm.call_count == 1
    assert mock_stop.call_count == 0
    assert mock_start.call_count == 0
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_confirm_has_default_true(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_dynamic_field_name: Mock,
    mock_is_service_running: Mock,
    directory: Path,
) -> None:
    mock_echo.confirm.return_value = True

    set(directory=directory, env_name="DF_SOME_VAR", env_value="value", df_prefix=True, no_restart=False)

    assert mock_echo.confirm.call_args == mock.call("Restart the server now to apply the change?", default=True)
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_skips_restart_when_no_restart_flag(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_dynamic_field_name: Mock,
    mock_is_service_running: Mock,
    directory: Path,
) -> None:
    set(directory=directory, env_name="DF_SOME_VAR", env_value="value", df_prefix=True, no_restart=True)

    assert mock_env_set.call_count == 1
    assert mock_echo.confirm.call_count == 0
    assert mock_stop.call_count == 0
    assert mock_start.call_count == 0
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value="otel_tracing_enabled")
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_blocks_when_variable_is_dynamic_config(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_dynamic_field_name: Mock,
    directory: Path,
) -> None:
    with pytest.raises(typer.Exit):
        set(directory=directory, env_name="DF_OTEL_TRACING_ENABLED", env_value="true", df_prefix=True, no_restart=False)

    assert mock_env_set.call_count == 0
    assert mock_echo.error.call_count == 1
    assert "otel_tracing_enabled" in mock_echo.error.call_args[0][0]
    assert mock_stop.call_count == 0
    assert mock_start.call_count == 0
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
def test_dynamic_field_name_returns_none_when_server_not_running(
    mock_is_service_running: Mock,
    directory: Path,
) -> None:
    result = _dynamic_field_name(directory, "DF_OTEL_TRACING_ENABLED")

    assert result is None


@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=True)
def test_dynamic_field_name_returns_none_when_port_missing(
    mock_is_service_running: Mock,
    directory: Path,
) -> None:
    result = _dynamic_field_name(directory, "DF_OTEL_TRACING_ENABLED")

    assert result is None


def test_resolved_env_name_adds_prefix_when_missing() -> None:
    result = _resolved_env_name("some_var", True)

    assert result == "DF_SOME_VAR"


def test_resolved_env_name_keeps_prefix_when_already_present() -> None:
    result = _resolved_env_name("DF_SOME_VAR", True)

    assert result == "DF_SOME_VAR"


@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=True)
def test_dynamic_field_name_returns_none_when_token_key_missing(
    mock_is_service_running: Mock,
    directory: Path,
) -> None:
    (directory / ".env").write_text("DF_SERVER_PORT=8000\n")
    secrets_file = directory / "secrets"
    secrets_file.write_text("SOME_OTHER_KEY=abc\n")
    state.cli_secrets_file = secrets_file

    result = _dynamic_field_name(directory, "DF_OTEL_TRACING_ENABLED")

    assert result is None


@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=True)
def test_dynamic_field_name_returns_none_when_no_user_token_stored(
    mock_is_service_running: Mock,
    directory: Path,
) -> None:
    (directory / ".env").write_text("DF_SERVER_PORT=8000\n")
    secrets_file = directory / "secrets"
    state.cli_secrets_file = secrets_file

    result = _dynamic_field_name(directory, "DF_OTEL_TRACING_ENABLED")

    assert result is None


@mock.patch("deepfellow.server.env_command.set.httpx.get")
@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=True)
def test_dynamic_field_name_returns_field_name_when_key_is_dynamic(
    mock_is_service_running: Mock,
    mock_get: Mock,
    directory: Path,
) -> None:
    (directory / ".env").write_text("DF_SERVER_PORT=8000\n")
    secrets_file = directory / "secrets"
    secrets_file.write_text("DF_USER_TOKEN=abc\n")
    state.cli_secrets_file = secrets_file
    mock_get.return_value = Mock(json=lambda: {"otel_tracing_enabled": True})

    result = _dynamic_field_name(directory, "DF_OTEL_TRACING_ENABLED")

    assert result == "otel_tracing_enabled"
    assert mock_get.call_count == 1


@mock.patch("deepfellow.server.env_command.set.httpx.get")
@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=True)
def test_dynamic_field_name_requests_admin_config_on_bind_address(
    mock_is_service_running: Mock,
    mock_get: Mock,
    directory: Path,
) -> None:
    (directory / ".env").write_text("DF_SERVER_PORT=8000\nDF_SERVER_BIND_ADDRESS=10.0.0.5\n")
    secrets_file = directory / "secrets"
    secrets_file.write_text("DF_USER_TOKEN=abc\n")
    state.cli_secrets_file = secrets_file
    mock_get.return_value = Mock(json=dict)

    _dynamic_field_name(directory, "DF_OTEL_TRACING_ENABLED")

    assert mock_get.call_args.args[0] == "http://10.0.0.5:8000/admin/config"


@mock.patch("deepfellow.server.env_command.set.httpx.get")
@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=True)
def test_dynamic_field_name_returns_none_when_key_not_in_dynamic_config(
    mock_is_service_running: Mock,
    mock_get: Mock,
    directory: Path,
) -> None:
    (directory / ".env").write_text("DF_SERVER_PORT=8000\n")
    secrets_file = directory / "secrets"
    secrets_file.write_text("DF_USER_TOKEN=abc\n")
    state.cli_secrets_file = secrets_file
    mock_get.return_value = Mock(json=lambda: {"otel_tracing_enabled": True})

    result = _dynamic_field_name(directory, "DF_MONGO_URL")

    assert result is None


@mock.patch("deepfellow.server.env_command.set.httpx.get", side_effect=httpx.ConnectError("boom"))
@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=True)
def test_dynamic_field_name_returns_none_when_admin_api_unreachable(
    mock_is_service_running: Mock,
    mock_get: Mock,
    directory: Path,
) -> None:
    (directory / ".env").write_text("DF_SERVER_PORT=8000\n")
    secrets_file = directory / "secrets"
    secrets_file.write_text("DF_USER_TOKEN=abc\n")
    state.cli_secrets_file = secrets_file

    result = _dynamic_field_name(directory, "DF_OTEL_TRACING_ENABLED")

    assert result is None


@mock.patch("deepfellow.server.env_command.set.config_json_exists", return_value=True)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_warns_when_config_json_exists_and_server_not_running(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_is_service_running: Mock,
    mock_dynamic_field_name: Mock,
    mock_config_json_exists: Mock,
    directory: Path,
) -> None:
    mock_echo.confirm.return_value = False

    set(directory=directory, env_name="DF_SOME_VAR", env_value="value", df_prefix=True, no_restart=False)

    assert mock_echo.warning.call_count == 1
    assert mock_env_set.call_count == 1
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.env_command.set.config_json_exists", return_value=False)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_no_warning_when_config_json_missing_and_server_not_running(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_is_service_running: Mock,
    mock_dynamic_field_name: Mock,
    mock_config_json_exists: Mock,
    directory: Path,
) -> None:
    mock_echo.confirm.return_value = False

    set(directory=directory, env_name="DF_SOME_VAR", env_value="value", df_prefix=True, no_restart=False)

    assert mock_echo.warning.call_count == 0
    assert mock_env_set.call_count == 1
    assert mock_assert_docker.call_count == 1


# start_server()'s `docker compose up -d` recreates the worker when its resolved environment changed
# (and `--scale nightshift=0` keeps it down outside its shift window), so these variables need no
# Nightshift-specific handling - just the same restart as any other variable.
@pytest.mark.parametrize("env_name", ["DF_RABBITMQ_URL", "DF_RABBITMQ_USER", "DF_RABBITMQ_PASSWORD"])
@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_nightshift_variable_is_applied_by_the_regular_server_restart_only(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_dynamic_field_name: Mock,
    mock_is_service_running: Mock,
    env_name: str,
    directory: Path,
) -> None:
    mock_echo.confirm.return_value = True

    set(directory=directory, env_name=env_name, env_value="new-value", df_prefix=True, no_restart=False)

    assert mock_env_set.call_count == 1
    assert mock_stop.call_args == mock.call(directory)
    assert mock_start.call_args == mock.call(directory)


@pytest.mark.parametrize(
    ("env_name", "stored", "expected_args"),
    [
        (
            "DF_NIGHTSHIFT_STOP",
            {"df_nightshift_mode": "shift", "df_nightshift_start": "22:00"},
            ("shift", "22:00", "07:00"),
        ),
        (
            "DF_NIGHTSHIFT_MODE",
            {"df_nightshift_start": "22:00", "df_nightshift_stop": "06:00"},
            ("shift", "22:00", "06:00"),
        ),
        ("DF_NIGHTSHIFT_START", {}, ("always", "07:00", "")),
    ],
    ids=["stop_with_stored_start", "mode_with_stored_hours", "start_with_nothing_stored"],
)
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.apply_nightshift_schedule")
@mock.patch("deepfellow.server.env_command.set.read_env_file_to_dict")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_nightshift_schedule_key_regenerates_timers_with_the_resulting_values(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read_env: Mock,
    mock_apply: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    env_name: str,
    stored: dict,
    expected_args: tuple[str, str, str],
    directory: Path,
) -> None:
    """The timers are derived from these keys - so `env set` must go through the same pipeline as
    `nightshift mode`/`schedule` instead of just writing .env, which left them out of sync."""
    mock_read_env.return_value = stored
    new_value = {"DF_NIGHTSHIFT_STOP": "07:00", "DF_NIGHTSHIFT_MODE": "shift", "DF_NIGHTSHIFT_START": "07:00"}[env_name]

    set(directory=directory, env_name=env_name, env_value=new_value, df_prefix=True, no_restart=False)

    assert mock_apply.call_args == mock.call(directory, *expected_args, {env_name: new_value})
    # applied through the shared pipeline only: no plain .env write, no server restart offered
    assert mock_env_set.call_count == 0
    assert mock_echo.confirm.call_count == 0


@pytest.mark.parametrize("env_name", ["DF_NIGHTSHIFT_START", "DF_NIGHTSHIFT_STOP"])
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.apply_nightshift_schedule")
@mock.patch("deepfellow.server.env_command.set.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_nightshift_hour_rejects_a_malformed_value_even_when_the_mode_is_always(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read_env: Mock,
    mock_apply: Mock,
    mock_env_set: Mock,
    env_name: str,
    directory: Path,
) -> None:
    """Outside `shift` the hours aren't validated as a schedule, so the written value itself has to be -
    otherwise garbage lands in .env and only surfaces at the next `nightshift mode shift`."""
    with pytest.raises(typer.BadParameter):
        set(directory=directory, env_name=env_name, env_value="not-a-time", df_prefix=True, no_restart=False)

    assert mock_apply.call_count == 0
    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.apply_nightshift_schedule")
@mock.patch("deepfellow.server.env_command.set.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_nightshift_hour_accepts_clearing_it_with_an_empty_value(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read_env: Mock,
    mock_apply: Mock,
    mock_echo: Mock,
    directory: Path,
) -> None:
    set(directory=directory, env_name="DF_NIGHTSHIFT_START", env_value="", df_prefix=True, no_restart=False)

    assert mock_apply.call_args == mock.call(directory, "always", "", "", {"DF_NIGHTSHIFT_START": ""})


@pytest.mark.parametrize(
    ("env_name", "env_value", "expected"),
    [
        ("DF_SERVER_BIND_ADDRESS", "::1", "[::1]"),
        ("SERVER_BIND_ADDRESS", "127.0.0.1", "127.0.0.1"),
        ("INTERNAL_BIND_ADDRESS", "", ""),
    ],
)
@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_writes_normalized_bind_address(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_dynamic_field_name: Mock,
    mock_is_service_running: Mock,
    env_name: str,
    env_value: str,
    expected: str,
    directory: Path,
) -> None:
    set(directory=directory, env_name=env_name, env_value=env_value, df_prefix=True, no_restart=True)

    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == mock.call(directory / ".env", env_name, expected, True)


@pytest.mark.parametrize(
    ("env_name", "env_value"),
    [
        ("DF_SERVER_BIND_ADDRESS", "localhost"),
        ("INTERNAL_BIND_ADDRESS", "[::1"),
    ],
)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_rejects_invalid_bind_address_before_writing(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_dynamic_field_name: Mock,
    env_name: str,
    env_value: str,
    directory: Path,
) -> None:
    with pytest.raises(typer.BadParameter):
        set(directory=directory, env_name=env_name, env_value=env_value, df_prefix=True, no_restart=True)

    assert mock_dynamic_field_name.call_count == 0
    assert mock_env_set.call_count == 0


@pytest.mark.parametrize(
    ("stored_url", "new_bind", "expected_url", "expected_warning"),
    [
        ("http://localhost:8000", "10.0.0.5", "http://10.0.0.5:8000", False),
        ("http://10.0.0.5:8000", "", "http://localhost:8000", False),
        ("https://deepfellow.example.com", "10.0.0.5", None, True),
        ("http://localhost:8000", "0.0.0.0", None, False),
        (None, "10.0.0.5", None, False),
    ],
)
@mock.patch("deepfellow.server.env_command.set.config_json_exists", return_value=False)
@mock.patch("deepfellow.server.env_command.set.state")
@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_bind_address_retargets_stored_server_url(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_dynamic_field_name: Mock,
    mock_is_service_running: Mock,
    mock_state: Mock,
    mock_config_json_exists: Mock,
    stored_url: str | None,
    new_bind: str,
    expected_url: str | None,
    expected_warning: bool,
    directory: Path,
) -> None:
    old_bind = "10.0.0.5" if stored_url == "http://10.0.0.5:8000" else ""
    (directory / ".env").write_text(f"DF_SERVER_PORT=8000\nDF_SERVER_BIND_ADDRESS={old_bind}\n")
    mock_state.cli_config = {"df_server_url": stored_url} if stored_url else {}

    set(directory=directory, env_name="SERVER_BIND_ADDRESS", env_value=new_bind, df_prefix=True, no_restart=True)

    config_writes = [c for c in mock_env_set.call_args_list if c.args[0] == mock_state.cli_config_file]
    if expected_url is None:
        assert config_writes == []
    else:
        assert config_writes == [
            mock.call(mock_state.cli_config_file, "DF_SERVER_URL", expected_url, should_raise=False, docker_note=False)
        ]
    assert mock_echo.warning.call_count == int(expected_warning)


@pytest.mark.parametrize("env_name", ["INTERNAL_BIND_ADDRESS", "SOME_VAR"])
@mock.patch("deepfellow.server.env_command.set.config_json_exists", return_value=False)
@mock.patch("deepfellow.server.env_command.set.state")
@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_other_variable_leaves_stored_server_url_alone(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_dynamic_field_name: Mock,
    mock_is_service_running: Mock,
    mock_state: Mock,
    mock_config_json_exists: Mock,
    env_name: str,
    directory: Path,
) -> None:
    (directory / ".env").write_text("DF_SERVER_PORT=8000\n")
    mock_state.cli_config = {"df_server_url": "http://localhost:8000"}

    set(directory=directory, env_name=env_name, env_value="", df_prefix=True, no_restart=True)

    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args.args[0] == directory / ".env"


@mock.patch("deepfellow.server.env_command.set.httpx.get")
@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=True)
def test_dynamic_field_name_returns_rabbitmq_when_server_has_rabbitmq_section(
    mock_is_service_running: Mock,
    mock_get: Mock,
    directory: Path,
) -> None:
    (directory / ".env").write_text("DF_SERVER_PORT=8000\n")
    secrets_file = directory / "secrets"
    secrets_file.write_text("DF_USER_TOKEN=abc\n")
    state.cli_secrets_file = secrets_file
    mock_get.return_value = Mock(json=lambda: {"rabbitmq": {"host": "mq", "port": 5672}})

    result = _dynamic_field_name(directory, "DF_RABBITMQ_URL")

    assert result == "rabbitmq"


@mock.patch("deepfellow.server.env_command.set.httpx.get")
@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=True)
def test_dynamic_field_name_returns_none_for_rabbitmq_when_server_has_no_rabbitmq_section(
    mock_is_service_running: Mock,
    mock_get: Mock,
    directory: Path,
) -> None:
    (directory / ".env").write_text("DF_SERVER_PORT=8000\n")
    secrets_file = directory / "secrets"
    secrets_file.write_text("DF_USER_TOKEN=abc\n")
    state.cli_secrets_file = secrets_file
    mock_get.return_value = Mock(json=lambda: {"otel_tracing_enabled": True})

    result = _dynamic_field_name(directory, "DF_RABBITMQ_URL")

    assert result is None


@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value="rabbitmq")
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_blocks_rabbitmq_variable_when_server_has_rabbitmq_section(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_dynamic_field_name: Mock,
    directory: Path,
) -> None:
    with pytest.raises(typer.Exit):
        set(directory=directory, env_name="DF_RABBITMQ_URL", env_value="mq:5672", df_prefix=True, no_restart=False)

    assert mock_env_set.call_count == 0
    assert mock_echo.error.call_count == 1
    assert "server config set" in mock_echo.error.call_args[0][0]
    assert "rabbitmq=" in mock_echo.error.call_args[0][0]
    assert mock_stop.call_count == 0
    assert mock_start.call_count == 0


@pytest.mark.parametrize("env_name", ["DF_RABBITMQ_USER", "DF_RABBITMQ_PASSWORD"])
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value="rabbitmq")
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_writes_env_and_warns_for_local_rabbitmq_credentials(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_dynamic_field_name: Mock,
    env_name: str,
    directory: Path,
) -> None:
    (directory / "compose.yaml").write_text("services:\n  rabbitmq:\n    image: rabbitmq\n")
    mock_echo.confirm.return_value = True

    set(directory=directory, env_name=env_name, env_value="new-value", df_prefix=True, no_restart=False)

    assert mock_env_set.call_count == 1
    assert mock_echo.error.call_count == 0
    assert mock_echo.warning.call_count == 1
    assert "server config set" in mock_echo.warning.call_args[0][0]
    assert mock_stop.call_count == 1
    assert mock_start.call_count == 1


@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value="rabbitmq")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.assert_docker")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_blocks_rabbitmq_url_even_with_local_rabbitmq(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    mock_dynamic_field_name: Mock,
    directory: Path,
) -> None:
    (directory / "compose.yaml").write_text("services:\n  rabbitmq:\n    image: rabbitmq\n")

    with pytest.raises(typer.Exit):
        set(directory=directory, env_name="DF_RABBITMQ_URL", env_value="mq:5672", df_prefix=True, no_restart=False)

    assert mock_env_set.call_count == 0
    assert mock_echo.error.call_count == 1
