# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the server env info command."""

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.server.env_command.info import ENV_METADATA, _config_json_exists, info


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    return tmp_path


@mock.patch("deepfellow.server.env_command.info._config_json_exists", return_value=False)
@mock.patch("deepfellow.server.env_command.info.print_env_info")
@mock.patch("deepfellow.server.env_command.info.get_envs_list")
@mock.patch("deepfellow.server.env_command.info.check_server_directory")
def test_doc_mode_calls_print_env_info(
    mock_check: Mock, mock_envs: Mock, mock_print: Mock, mock_config_json: Mock, directory: Path
):
    mock_envs.return_value = ["DF_SERVER_PORT=8000"]

    info(directory=directory, secret=False, doc=True)

    assert mock_print.call_count == 1
    assert mock_print.call_args == mock.call(
        "Information about DeepFellow Server:",
        ENV_METADATA,
        {"DF_SERVER_PORT": "8000"},
        show_secret=False,
        doc=True,
        show_prefix=True,
    )


@mock.patch("deepfellow.server.env_command.info._config_json_exists", return_value=False)
@mock.patch("deepfellow.server.env_command.info.print_env_info")
@mock.patch("deepfellow.server.env_command.info.get_envs_list")
@mock.patch("deepfellow.server.env_command.info.check_server_directory")
def test_normal_mode_calls_print_env_info(
    mock_check: Mock, mock_envs: Mock, mock_print: Mock, mock_config_json: Mock, directory: Path
):
    mock_envs.return_value = ["DF_SERVER_PORT=8000"]

    info(directory=directory, secret=False, doc=False)

    assert mock_print.call_count == 1
    assert mock_print.call_args == mock.call(
        "Information about DeepFellow Server:",
        ENV_METADATA,
        {"DF_SERVER_PORT": "8000"},
        show_secret=False,
        doc=False,
        show_prefix=True,
    )


@mock.patch("deepfellow.server.env_command.info._config_json_exists", return_value=False)
@mock.patch("deepfellow.server.env_command.info.print_env_info")
@mock.patch("deepfellow.server.env_command.info.get_envs_list")
@mock.patch("deepfellow.server.env_command.info.check_server_directory")
def test_show_secret_passed_to_print_env_info(
    mock_check: Mock, mock_envs: Mock, mock_print: Mock, mock_config_json: Mock, directory: Path
):
    mock_envs.return_value = ["DF_MONGO_PASSWORD=pass123"]

    info(directory=directory, secret=True, doc=False)

    assert mock_print.call_args == mock.call(
        "Information about DeepFellow Server:",
        ENV_METADATA,
        {"DF_MONGO_PASSWORD": "pass123"},
        show_secret=True,
        doc=False,
        show_prefix=True,
    )


@mock.patch("deepfellow.server.env_command.info._config_json_exists", return_value=True)
@mock.patch("deepfellow.server.env_command.info.echo")
@mock.patch("deepfellow.server.env_command.info.print_env_info")
@mock.patch("deepfellow.server.env_command.info.get_envs_list")
@mock.patch("deepfellow.server.env_command.info.check_server_directory")
def test_config_json_exists_warns(
    mock_check: Mock, mock_envs: Mock, mock_print: Mock, mock_echo: Mock, mock_config_json: Mock, directory: Path
):
    mock_envs.return_value = ["DF_SERVER_PORT=8000"]

    info(directory=directory, secret=False, doc=False)

    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.server.env_command.info._config_json_exists", return_value=False)
@mock.patch("deepfellow.server.env_command.info.echo")
@mock.patch("deepfellow.server.env_command.info.print_env_info")
@mock.patch("deepfellow.server.env_command.info.get_envs_list")
@mock.patch("deepfellow.server.env_command.info.check_server_directory")
def test_config_json_missing_does_not_warn(
    mock_check: Mock, mock_envs: Mock, mock_print: Mock, mock_echo: Mock, mock_config_json: Mock, directory: Path
):
    mock_envs.return_value = ["DF_SERVER_PORT=8000"]

    info(directory=directory, secret=False, doc=False)

    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.server.env_command.info.DF_SERVER_STORAGE_DIRECTORY")
def test_config_json_exists_checks_fixed_storage_dir(mock_storage_dir: Mock, tmp_path: Path) -> None:
    mock_storage_dir.__truediv__.side_effect = lambda name: tmp_path / name
    (tmp_path / "config.json").write_text("{}")

    assert _config_json_exists() is True


@mock.patch("deepfellow.server.env_command.info.DF_SERVER_STORAGE_DIRECTORY")
def test_config_json_exists_returns_false_when_missing(mock_storage_dir: Mock, tmp_path: Path) -> None:
    mock_storage_dir.__truediv__.side_effect = lambda name: tmp_path / name

    assert _config_json_exists() is False
