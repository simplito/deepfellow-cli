# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the top-level infra info command."""

import json
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import httpx
import pytest
import typer
from typer.testing import CliRunner

from deepfellow.common.state import state
from deepfellow.infra.info import ENV_METADATA, _dynamic_config_values, app, info

SERVER = "http://localhost:8086"

runner = CliRunner()


@pytest.fixture
def no_secrets_file(tmp_path: Path) -> Path:
    """A secrets file path that does not exist, so no admin key can be read from it."""
    secrets_file = tmp_path / "secrets"
    state.cli_secrets_file = secrets_file
    return secrets_file


@mock.patch("deepfellow.infra.info._dynamic_config_values")
@mock.patch("deepfellow.infra.info.print_env_info")
def test_doc_mode_calls_print_env_info(mock_print: Mock, mock_dynamic: Mock):
    mock_dynamic.return_value = {"DF_NAME": "myinfra"}

    info(server=None, api_key=None, secret=False, doc=True)

    assert mock_print.call_count == 1
    assert mock_print.call_args == mock.call(
        "Information about DeepFellow Infra:",
        ENV_METADATA,
        {"DF_NAME": "myinfra"},
        show_secret=False,
        doc=True,
    )


@mock.patch("deepfellow.infra.info._dynamic_config_values")
@mock.patch("deepfellow.infra.info.print_env_info")
def test_normal_mode_calls_print_env_info(mock_print: Mock, mock_dynamic: Mock):
    mock_dynamic.return_value = {"DF_NAME": "myinfra"}

    info(server=None, api_key=None, secret=False, doc=False)

    assert mock_print.call_count == 1
    assert mock_print.call_args == mock.call(
        "Information about DeepFellow Infra:",
        ENV_METADATA,
        {"DF_NAME": "myinfra"},
        show_secret=False,
        doc=False,
    )


@mock.patch("deepfellow.infra.info._dynamic_config_values")
@mock.patch("deepfellow.infra.info.print_env_info")
def test_infra_url_derives_mesh_url(mock_print: Mock, mock_dynamic: Mock):
    mock_dynamic.return_value = {"DF_INFRA_URL": "http://localhost:8080"}

    info(server=None, api_key=None, secret=False, doc=False)

    env_values_passed = mock_print.call_args[0][2]
    assert env_values_passed["DF_INFRA_MESH_URL"] == "ws://localhost:8080"


@mock.patch("deepfellow.infra.info._dynamic_config_values")
@mock.patch("deepfellow.infra.info.print_env_info")
def test_infra_url_https_derives_wss_mesh_url(mock_print: Mock, mock_dynamic: Mock):
    mock_dynamic.return_value = {"DF_INFRA_URL": "https://example.com"}

    info(server=None, api_key=None, secret=False, doc=False)

    env_values_passed = mock_print.call_args[0][2]
    assert env_values_passed["DF_INFRA_MESH_URL"] == "wss://example.com"


@mock.patch("deepfellow.infra.info._dynamic_config_values")
@mock.patch("deepfellow.infra.info.print_env_info")
def test_show_secret_passed_to_print_env_info(mock_print: Mock, mock_dynamic: Mock):
    mock_dynamic.return_value = {"DF_MESH_KEY": "verysecret"}

    info(server=None, api_key=None, secret=True, doc=False)

    assert mock_print.call_args == mock.call(
        "Information about DeepFellow Infra:",
        ENV_METADATA,
        {"DF_MESH_KEY": "verysecret"},
        show_secret=True,
        doc=False,
    )


@mock.patch("deepfellow.infra.info._dynamic_config_values")
@mock.patch("deepfellow.infra.info.print_env_info")
def test_info_passes_server_and_api_key_through(mock_print: Mock, mock_dynamic: Mock):
    mock_dynamic.return_value = {}

    info(server="http://remote:8086", api_key="explicit-key", secret=True, doc=False)

    assert mock_dynamic.call_args == mock.call("http://remote:8086", "explicit-key", True)


def test_dynamic_config_values_exits_when_nothing_resolvable(no_secrets_file: Path) -> None:
    state.cli_config = {}

    with pytest.raises(typer.Exit) as exc_info:
        _dynamic_config_values(server=None, api_key=None, secret=False)

    assert exc_info.value.exit_code == 1


def test_dynamic_config_values_exits_when_server_resolvable_but_no_key(no_secrets_file: Path) -> None:
    state.cli_config = {}

    with pytest.raises(typer.Exit) as exc_info:
        _dynamic_config_values(server=SERVER, api_key=None, secret=False)

    assert exc_info.value.exit_code == 1


@mock.patch("deepfellow.infra.info.httpx.get")
def test_dynamic_config_values_uses_explicit_server_and_api_key(mock_get: Mock, no_secrets_file: Path) -> None:
    mock_get.return_value = Mock(
        json=lambda: {"entries": [{"key": "DF_OTEL_TRACING_ENABLED", "value": True, "is_secret": False}]}
    )

    result = _dynamic_config_values(server=SERVER, api_key="explicit-key", secret=False)

    assert result == {"DF_OTEL_TRACING_ENABLED": "True"}
    assert mock_get.call_args == mock.call(
        f"{SERVER}/admin/config", headers={"Authorization": "Bearer explicit-key"}, timeout=5.0
    )


@mock.patch("deepfellow.infra.info.httpx.get")
def test_dynamic_config_values_falls_back_to_stored_server_and_key(mock_get: Mock, tmp_path: Path) -> None:
    state.cli_config = {"df_infra_external_url": SERVER}
    secrets_file = tmp_path / "secrets"
    secrets_file.write_text("DF_INFRA_ADMIN_API_KEY=stored-key\n")
    state.cli_secrets_file = secrets_file
    mock_get.return_value = Mock(json=lambda: {"entries": [{"key": "DF_XYZ", "value": "123", "is_secret": False}]})

    result = _dynamic_config_values(server=None, api_key=None, secret=False)

    assert result == {"DF_XYZ": "123"}
    assert mock_get.call_args == mock.call(
        f"{SERVER}/admin/config", headers={"Authorization": "Bearer stored-key"}, timeout=5.0
    )


@mock.patch("deepfellow.infra.info.httpx.get")
def test_dynamic_config_values_skips_entries_without_key_or_value(mock_get: Mock, no_secrets_file: Path) -> None:
    mock_get.return_value = Mock(
        json=lambda: {
            "entries": [
                {"key": "DF_OTEL_TRACING_ENABLED", "value": True, "is_secret": False},
                {"key": "DF_MESH_KEY", "value": None, "is_secret": True},
                {"value": "orphaned", "is_secret": False},
            ]
        }
    )

    result = _dynamic_config_values(server=SERVER, api_key="explicit-key", secret=False)

    assert result == {"DF_OTEL_TRACING_ENABLED": "True"}


@mock.patch("deepfellow.infra.info.httpx.get")
def test_dynamic_config_values_reveals_secrets_when_requested(mock_get: Mock, no_secrets_file: Path) -> None:
    def _get(url: str, **kwargs: object) -> Mock:
        if url.endswith("/reveal"):
            return Mock(json=lambda: {"value": "revealed"})
        return Mock(
            json=lambda: {"entries": [{"key": "DF_MESH_KEY", "value": "••••••••", "is_secret": True}]},
        )

    mock_get.side_effect = _get

    result = _dynamic_config_values(server=SERVER, api_key="explicit-key", secret=True)

    assert result == {"DF_MESH_KEY": "revealed"}
    assert mock_get.call_count == 2


@mock.patch("deepfellow.infra.info.httpx.get", side_effect=httpx.ConnectError("boom"))
def test_dynamic_config_values_exits_when_admin_api_unreachable(mock_get: Mock, no_secrets_file: Path) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        _dynamic_config_values(server=SERVER, api_key="explicit-key", secret=False)

    assert exc_info.value.exit_code == 1


@mock.patch("deepfellow.infra.info.httpx.get")
def test_dynamic_config_values_exits_when_response_is_not_json(mock_get: Mock, no_secrets_file: Path) -> None:
    """Regression: a reachable server that isn't actually the admin API yet."""
    mock_get.return_value = Mock(json=Mock(side_effect=json.JSONDecodeError("Expecting value", "", 0)))

    with pytest.raises(typer.Exit) as exc_info:
        _dynamic_config_values(server=SERVER, api_key="explicit-key", secret=False)

    assert exc_info.value.exit_code == 1


@mock.patch("deepfellow.infra.info.httpx.get")
def test_dynamic_config_values_exits_when_response_is_not_a_dict(mock_get: Mock, no_secrets_file: Path) -> None:
    mock_get.return_value = Mock(json=lambda: ["unexpected", "list"])

    with pytest.raises(typer.Exit) as exc_info:
        _dynamic_config_values(server=SERVER, api_key="explicit-key", secret=False)

    assert exc_info.value.exit_code == 1


def test_info_cli_rejects_old_server_option():
    result = runner.invoke(app, ["--server", SERVER])

    assert result.exit_code == 2
    assert "no such option: --server" in result.output.lower()


@mock.patch("deepfellow.infra.info._dynamic_config_values", return_value={})
@mock.patch("deepfellow.infra.info.print_env_info")
def test_info_cli_accepts_url_option(mock_print: Mock, mock_dynamic: Mock):
    result = runner.invoke(app, ["--url", SERVER])

    assert result.exit_code == 0
    assert mock_dynamic.call_args == mock.call(SERVER, None, False)
