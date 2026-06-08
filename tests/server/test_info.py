# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the top-level server info command."""

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.server.env_command.info import ENV_METADATA
from deepfellow.server.info import info


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    return tmp_path


@mock.patch("deepfellow.server.env_command.info.print_env_info")
@mock.patch("deepfellow.server.env_command.info.get_envs_list")
@mock.patch("deepfellow.server.env_command.info.check_server_directory")
def test_info_calls_print_env_info_without_prefix(mock_check: Mock, mock_envs: Mock, mock_print: Mock, directory: Path):
    mock_envs.return_value = ["DF_SERVER_PORT=8000"]

    info(directory=directory, secret=False, doc=False)

    assert mock_print.call_count == 1
    assert mock_print.call_args == mock.call(
        "Information about DeepFellow Server:",
        ENV_METADATA,
        {"DF_SERVER_PORT": "8000"},
        show_secret=False,
        doc=False,
        show_prefix=False,
    )


@mock.patch("deepfellow.server.env_command.info.print_env_info")
@mock.patch("deepfellow.server.env_command.info.get_envs_list")
@mock.patch("deepfellow.server.env_command.info.check_server_directory")
def test_info_passes_show_secret_and_doc(mock_check: Mock, mock_envs: Mock, mock_print: Mock, directory: Path):
    mock_envs.return_value = ["DF_MONGO_PASSWORD=pass123"]

    info(directory=directory, secret=True, doc=True)

    assert mock_print.call_args == mock.call(
        "Information about DeepFellow Server:",
        ENV_METADATA,
        {"DF_MONGO_PASSWORD": "pass123"},
        show_secret=True,
        doc=True,
        show_prefix=False,
    )
