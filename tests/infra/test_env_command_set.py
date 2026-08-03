# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the infra env set command."""

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import httpx
import pytest
import typer

from deepfellow.infra.env_command.set import _config_json_exists, _dynamic_field_name, _resolved_env_name, set


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    return tmp_path


@pytest.mark.parametrize(
    ("env_name", "df_prefix", "expected"),
    [
        ("some_var", True, "DF_SOME_VAR"),
        ("DF_SOME_VAR", True, "DF_SOME_VAR"),
        ("some_var", False, "SOME_VAR"),
    ],
)
def test_resolved_env_name_applies_df_prefix(env_name: str, df_prefix: bool, expected: str) -> None:
    result = _resolved_env_name(env_name, df_prefix)

    assert result == expected


@mock.patch("deepfellow.infra.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.infra.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.infra.env_command.set.start_infra")
@mock.patch("deepfellow.infra.env_command.set.stop_infra")
@mock.patch("deepfellow.infra.env_command.set.echo")
@mock.patch("deepfellow.infra.env_command.set.env_set")
@mock.patch("deepfellow.infra.env_command.set.check_infra_directory")
def test_set_restarts_infra_when_confirmed(
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


@mock.patch("deepfellow.infra.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.infra.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.infra.env_command.set.start_infra")
@mock.patch("deepfellow.infra.env_command.set.stop_infra")
@mock.patch("deepfellow.infra.env_command.set.echo")
@mock.patch("deepfellow.infra.env_command.set.env_set")
@mock.patch("deepfellow.infra.env_command.set.check_infra_directory")
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


@mock.patch("deepfellow.infra.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.infra.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.infra.env_command.set.start_infra")
@mock.patch("deepfellow.infra.env_command.set.stop_infra")
@mock.patch("deepfellow.infra.env_command.set.echo")
@mock.patch("deepfellow.infra.env_command.set.env_set")
@mock.patch("deepfellow.infra.env_command.set.check_infra_directory")
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

    assert mock_echo.confirm.call_args == mock.call("Restart the infra now to apply the change?", default=True)


@mock.patch("deepfellow.infra.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.infra.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.infra.env_command.set.start_infra")
@mock.patch("deepfellow.infra.env_command.set.stop_infra")
@mock.patch("deepfellow.infra.env_command.set.echo")
@mock.patch("deepfellow.infra.env_command.set.env_set")
@mock.patch("deepfellow.infra.env_command.set.check_infra_directory")
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


@mock.patch("deepfellow.infra.env_command.set._dynamic_field_name", return_value="otel_tracing_enabled")
@mock.patch("deepfellow.infra.env_command.set.start_infra")
@mock.patch("deepfellow.infra.env_command.set.stop_infra")
@mock.patch("deepfellow.infra.env_command.set.echo")
@mock.patch("deepfellow.infra.env_command.set.env_set")
@mock.patch("deepfellow.infra.env_command.set.check_infra_directory")
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


@mock.patch("deepfellow.infra.env_command.set.is_service_running", return_value=False)
def test_dynamic_field_name_returns_none_when_infra_not_running(
    mock_is_service_running: Mock,
    directory: Path,
) -> None:
    result = _dynamic_field_name(directory, "DF_OTEL_TRACING_ENABLED")

    assert result is None


@mock.patch("deepfellow.infra.env_command.set.is_service_running", return_value=True)
def test_dynamic_field_name_returns_none_when_admin_credentials_missing(
    mock_is_service_running: Mock,
    directory: Path,
) -> None:
    result = _dynamic_field_name(directory, "DF_OTEL_TRACING_ENABLED")

    assert result is None


@mock.patch("deepfellow.infra.env_command.set.httpx.get")
@mock.patch("deepfellow.infra.env_command.set.is_service_running", return_value=True)
def test_dynamic_field_name_returns_field_name_for_editable_entry(
    mock_is_service_running: Mock,
    mock_get: Mock,
    directory: Path,
) -> None:
    (directory / ".env").write_text("DF_INFRA_PORT=8080\nDF_INFRA_ADMIN_API_KEY=secret\n")
    mock_get.return_value = Mock(
        json=lambda: {
            "entries": [
                {"key": "DF_OTEL_TRACING_ENABLED", "is_editable": True, "field_name": "otel_tracing_enabled"},
            ]
        }
    )

    result = _dynamic_field_name(directory, "DF_OTEL_TRACING_ENABLED")

    assert result == "otel_tracing_enabled"
    assert mock_get.call_count == 1


@mock.patch("deepfellow.infra.env_command.set.httpx.get")
@mock.patch("deepfellow.infra.env_command.set.is_service_running", return_value=True)
def test_dynamic_field_name_returns_none_for_non_editable_entry(
    mock_is_service_running: Mock,
    mock_get: Mock,
    directory: Path,
) -> None:
    (directory / ".env").write_text("DF_INFRA_PORT=8080\nDF_INFRA_ADMIN_API_KEY=secret\n")
    mock_get.return_value = Mock(
        json=lambda: {
            "entries": [
                {"key": "DF_INFRA_DOCKER_SUBNET", "is_editable": False, "field_name": None},
            ]
        }
    )

    result = _dynamic_field_name(directory, "DF_INFRA_DOCKER_SUBNET")

    assert result is None


@mock.patch("deepfellow.infra.env_command.set.httpx.get", side_effect=httpx.ConnectError("boom"))
@mock.patch("deepfellow.infra.env_command.set.is_service_running", return_value=True)
def test_dynamic_field_name_returns_none_when_admin_api_unreachable(
    mock_is_service_running: Mock,
    mock_get: Mock,
    directory: Path,
) -> None:
    (directory / ".env").write_text("DF_INFRA_PORT=8080\nDF_INFRA_ADMIN_API_KEY=secret\n")

    result = _dynamic_field_name(directory, "DF_OTEL_TRACING_ENABLED")

    assert result is None


def test_config_json_exists_returns_true_when_file_present(directory: Path) -> None:
    (directory / ".env").write_text(f"DF_INFRA_STORAGE_DIR={directory}\n")
    (directory / "config.json").write_text("{}")

    result = _config_json_exists(directory)

    assert result is True


def test_config_json_exists_returns_false_when_file_absent(directory: Path) -> None:
    (directory / ".env").write_text(f"DF_INFRA_STORAGE_DIR={directory}\n")

    result = _config_json_exists(directory)

    assert result is False


@mock.patch("deepfellow.infra.env_command.set.DF_INFRA_STORAGE_DIR", Path("/nonexistent-default-storage-dir"))
def test_config_json_exists_falls_back_to_default_storage_dir_when_env_missing(directory: Path) -> None:
    result = _config_json_exists(directory)

    assert result is False


@mock.patch("deepfellow.infra.env_command.set._config_json_exists", return_value=True)
@mock.patch("deepfellow.infra.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.infra.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.infra.env_command.set.start_infra")
@mock.patch("deepfellow.infra.env_command.set.stop_infra")
@mock.patch("deepfellow.infra.env_command.set.echo")
@mock.patch("deepfellow.infra.env_command.set.env_set")
@mock.patch("deepfellow.infra.env_command.set.check_infra_directory")
def test_set_warns_when_config_json_exists_and_infra_not_running(
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


@mock.patch("deepfellow.infra.env_command.set._config_json_exists", return_value=False)
@mock.patch("deepfellow.infra.env_command.set._dynamic_field_name", return_value=None)
@mock.patch("deepfellow.infra.env_command.set.is_service_running", return_value=False)
@mock.patch("deepfellow.infra.env_command.set.start_infra")
@mock.patch("deepfellow.infra.env_command.set.stop_infra")
@mock.patch("deepfellow.infra.env_command.set.echo")
@mock.patch("deepfellow.infra.env_command.set.env_set")
@mock.patch("deepfellow.infra.env_command.set.check_infra_directory")
def test_set_no_warning_when_config_json_missing_and_infra_not_running(
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
