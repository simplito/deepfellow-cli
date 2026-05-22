# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the infra info command."""

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.infra.env_command.info import ENV_METADATA, info


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    return tmp_path


@mock.patch("deepfellow.infra.env_command.info.print_env_info")
@mock.patch("deepfellow.infra.env_command.info.get_envs_list")
@mock.patch("deepfellow.infra.env_command.info.check_infra_directory")
def test_doc_mode_calls_print_env_info(mock_check: Mock, mock_envs: Mock, mock_print: Mock, directory: Path):
    mock_envs.return_value = ["DF_NAME=myinfra"]

    info(directory=directory, secret=False, doc=True)

    assert mock_print.call_count == 1
    assert mock_print.call_args == mock.call(
        "Information about DeepFellow Infra:",
        ENV_METADATA,
        {"DF_NAME": "myinfra"},
        show_secret=False,
        doc=True,
    )


@mock.patch("deepfellow.infra.env_command.info.print_env_info")
@mock.patch("deepfellow.infra.env_command.info.get_envs_list")
@mock.patch("deepfellow.infra.env_command.info.check_infra_directory")
def test_normal_mode_calls_print_env_info(mock_check: Mock, mock_envs: Mock, mock_print: Mock, directory: Path):
    mock_envs.return_value = ["DF_NAME=myinfra"]

    info(directory=directory, secret=False, doc=False)

    assert mock_print.call_count == 1
    assert mock_print.call_args == mock.call(
        "Information about DeepFellow Infra:",
        ENV_METADATA,
        {"DF_NAME": "myinfra"},
        show_secret=False,
        doc=False,
    )


@mock.patch("deepfellow.infra.env_command.info.print_env_info")
@mock.patch("deepfellow.infra.env_command.info.get_envs_list")
@mock.patch("deepfellow.infra.env_command.info.check_infra_directory")
def test_infra_url_derives_mesh_url(mock_check: Mock, mock_envs: Mock, mock_print: Mock, directory: Path):
    mock_envs.return_value = ["DF_INFRA_URL=http://localhost:8080"]

    info(directory=directory, secret=False, doc=False)

    env_values_passed = mock_print.call_args[0][2]
    assert env_values_passed["DF_INFRA_MESH_URL"] == "ws://localhost:8080"


@mock.patch("deepfellow.infra.env_command.info.print_env_info")
@mock.patch("deepfellow.infra.env_command.info.get_envs_list")
@mock.patch("deepfellow.infra.env_command.info.check_infra_directory")
def test_infra_url_https_derives_wss_mesh_url(mock_check: Mock, mock_envs: Mock, mock_print: Mock, directory: Path):
    mock_envs.return_value = ["DF_INFRA_URL=https://example.com"]

    info(directory=directory, secret=False, doc=False)

    env_values_passed = mock_print.call_args[0][2]
    assert env_values_passed["DF_INFRA_MESH_URL"] == "wss://example.com"


@mock.patch("deepfellow.infra.env_command.info.print_env_info")
@mock.patch("deepfellow.infra.env_command.info.get_envs_list")
@mock.patch("deepfellow.infra.env_command.info.check_infra_directory")
def test_doc_mode_also_derives_mesh_url(mock_check: Mock, mock_envs: Mock, mock_print: Mock, directory: Path):
    mock_envs.return_value = ["DF_INFRA_URL=http://localhost:8080"]

    info(directory=directory, secret=False, doc=True)

    env_values_passed = mock_print.call_args[0][2]
    assert env_values_passed["DF_INFRA_MESH_URL"] == "ws://localhost:8080"


@mock.patch("deepfellow.infra.env_command.info.print_env_info")
@mock.patch("deepfellow.infra.env_command.info.get_envs_list")
@mock.patch("deepfellow.infra.env_command.info.check_infra_directory")
def test_show_secret_passed_to_print_env_info(mock_check: Mock, mock_envs: Mock, mock_print: Mock, directory: Path):
    mock_envs.return_value = ["DF_MESH_KEY=verysecret"]

    info(directory=directory, secret=True, doc=False)

    assert mock_print.call_args == mock.call(
        "Information about DeepFellow Infra:",
        ENV_METADATA,
        {"DF_MESH_KEY": "verysecret"},
        show_secret=True,
        doc=False,
    )
