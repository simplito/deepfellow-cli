# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the top-level server info command."""

import json
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import httpx
import pytest
import typer

from deepfellow.common.state import state
from deepfellow.server.info import ENV_METADATA, _dynamic_config_values, info

SERVER = "http://localhost:8000"


@pytest.fixture
def no_secrets_file(tmp_path: Path) -> Path:
    """A secrets file path that does not exist, so no user token can be read from it."""
    secrets_file = tmp_path / "secrets"
    state.cli_secrets_file = secrets_file
    return secrets_file


@mock.patch("deepfellow.server.info._dynamic_config_values")
@mock.patch("deepfellow.server.info.print_env_info")
def test_info_calls_print_env_info_without_prefix(mock_print: Mock, mock_dynamic: Mock):
    mock_dynamic.return_value = {"DF_SERVER_PORT": "8000"}

    info(server=None, secret=False, doc=False)

    assert mock_print.call_count == 1
    assert mock_print.call_args == mock.call(
        "Information about DeepFellow Server:",
        ENV_METADATA,
        {"DF_SERVER_PORT": "8000"},
        show_secret=False,
        doc=False,
    )


@mock.patch("deepfellow.server.info._dynamic_config_values")
@mock.patch("deepfellow.server.info.print_env_info")
def test_info_passes_show_secret_and_doc(mock_print: Mock, mock_dynamic: Mock):
    mock_dynamic.return_value = {"DF_MONGO_PASSWORD": "pass123"}

    info(server=None, secret=True, doc=True)

    assert mock_print.call_args == mock.call(
        "Information about DeepFellow Server:",
        ENV_METADATA,
        {"DF_MONGO_PASSWORD": "pass123"},
        show_secret=True,
        doc=True,
    )


@mock.patch("deepfellow.server.info._dynamic_config_values")
@mock.patch("deepfellow.server.info.print_env_info")
def test_info_passes_server_through(mock_print: Mock, mock_dynamic: Mock):
    mock_dynamic.return_value = {}

    info(server="http://remote:8000", secret=True, doc=False)

    assert mock_dynamic.call_args == mock.call("http://remote:8000", True)


def test_dynamic_config_values_exits_when_nothing_resolvable(no_secrets_file: Path) -> None:
    state.cli_config = {}

    with pytest.raises(typer.Exit) as exc_info:
        _dynamic_config_values(server=None, secret=False)

    assert exc_info.value.exit_code == 1


def test_dynamic_config_values_exits_when_no_user_token_stored(no_secrets_file: Path) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        _dynamic_config_values(server=SERVER, secret=False)

    assert exc_info.value.exit_code == 1


@mock.patch("deepfellow.server.info.httpx.get")
def test_dynamic_config_values_uses_explicit_server(mock_get: Mock, tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets"
    secrets_file.write_text("DF_USER_TOKEN=abc\n")
    state.cli_secrets_file = secrets_file
    mock_get.return_value = Mock(json=lambda: {"otel_tracing_enabled": True})

    result = _dynamic_config_values(server=SERVER, secret=False)

    assert result == {"DF_OTEL_TRACING_ENABLED": "True"}
    assert mock_get.call_args == mock.call(
        f"{SERVER}/admin/config", headers={"Authorization": "Bearer abc"}, timeout=5.0
    )


@mock.patch("deepfellow.server.info.httpx.get")
def test_dynamic_config_values_falls_back_to_stored_server(mock_get: Mock, tmp_path: Path) -> None:
    state.cli_config = {"df_server_url": SERVER}
    secrets_file = tmp_path / "secrets"
    secrets_file.write_text("DF_USER_TOKEN=abc\n")
    state.cli_secrets_file = secrets_file
    mock_get.return_value = Mock(json=lambda: {"otel_tracing_enabled": True})

    result = _dynamic_config_values(server=None, secret=False)

    assert result == {"DF_OTEL_TRACING_ENABLED": "True"}
    assert mock_get.call_args == mock.call(
        f"{SERVER}/admin/config", headers={"Authorization": "Bearer abc"}, timeout=5.0
    )


@mock.patch("deepfellow.server.info.httpx.get")
def test_dynamic_config_values_reveals_secrets_when_requested(mock_get: Mock, tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets"
    secrets_file.write_text("DF_USER_TOKEN=abc\n")
    state.cli_secrets_file = secrets_file

    def _get(url: str, **kwargs: object) -> Mock:
        if "/reveal/" in url:
            return Mock(json=lambda: {"value": "revealed"})
        return Mock(json=lambda: {"smtp": {"password": "••••••••"}})

    mock_get.side_effect = _get

    result = _dynamic_config_values(server=SERVER, secret=True)

    assert result == {"DF_SMTP__PASSWORD": "revealed"}
    assert mock_get.call_count == 2


@mock.patch("deepfellow.server.info.httpx.get", side_effect=httpx.ConnectError("boom"))
def test_dynamic_config_values_exits_when_admin_api_unreachable(mock_get: Mock, tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets"
    secrets_file.write_text("DF_USER_TOKEN=abc\n")
    state.cli_secrets_file = secrets_file

    with pytest.raises(typer.Exit) as exc_info:
        _dynamic_config_values(server=SERVER, secret=False)

    assert exc_info.value.exit_code == 1


@mock.patch("deepfellow.server.info.httpx.get")
def test_dynamic_config_values_exits_when_response_is_not_json(mock_get: Mock, tmp_path: Path) -> None:
    """Regression: a reachable server that isn't actually the admin API yet."""
    secrets_file = tmp_path / "secrets"
    secrets_file.write_text("DF_USER_TOKEN=abc\n")
    state.cli_secrets_file = secrets_file
    mock_get.return_value = Mock(json=Mock(side_effect=json.JSONDecodeError("Expecting value", "", 0)))

    with pytest.raises(typer.Exit) as exc_info:
        _dynamic_config_values(server=SERVER, secret=False)

    assert exc_info.value.exit_code == 1


@mock.patch("deepfellow.server.info.httpx.get")
def test_dynamic_config_values_exits_when_response_is_not_a_dict(mock_get: Mock, tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets"
    secrets_file.write_text("DF_USER_TOKEN=abc\n")
    state.cli_secrets_file = secrets_file
    mock_get.return_value = Mock(json=lambda: ["unexpected", "list"])

    with pytest.raises(typer.Exit) as exc_info:
        _dynamic_config_values(server=SERVER, secret=False)

    assert exc_info.value.exit_code == 1
