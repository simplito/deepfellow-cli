# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

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
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_restarts_server_when_confirmed(
    mock_check: Mock,
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


@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_skips_restart_when_declined(
    mock_check: Mock,
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


@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_confirm_has_default_true(
    mock_check: Mock,
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


@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_skips_restart_when_no_restart_flag(
    mock_check: Mock,
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


@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value="otel_tracing_enabled")
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_blocks_when_variable_is_dynamic_config(
    mock_check: Mock,
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
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_warns_when_config_json_exists_and_server_not_running(
    mock_check: Mock,
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


@mock.patch("deepfellow.server.env_command.set.config_json_exists", return_value=False)
@mock.patch("deepfellow.server.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.server.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.server.env_command.set.start_server")
@mock.patch("deepfellow.server.env_command.set.stop_server")
@mock.patch("deepfellow.server.env_command.set.echo")
@mock.patch("deepfellow.server.env_command.set.env_set")
@mock.patch("deepfellow.server.env_command.set.check_server_directory")
def test_set_no_warning_when_config_json_missing_and_server_not_running(
    mock_check: Mock,
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
