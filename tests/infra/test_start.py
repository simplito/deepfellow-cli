# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.infra.start import start


@pytest.fixture
def env_content() -> dict:
    return {"df_infra_port": "8080"}


@mock.patch("deepfellow.infra.start.start_infra")
@mock.patch("deepfellow.infra.start.echo.info")
@mock.patch("deepfellow.infra.start.read_env_file_to_dict")
@mock.patch("deepfellow.infra.start.check_infra_directory")
def test_start_calls_check_infra_directory(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_start_infra: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = env_content

    start(directory=directory)

    assert mock_check.call_count == 1
    assert mock_check.call_args == ((directory,), {})


@mock.patch("deepfellow.infra.start.start_infra")
@mock.patch("deepfellow.infra.start.echo.info")
@mock.patch("deepfellow.infra.start.read_env_file_to_dict")
@mock.patch("deepfellow.infra.start.check_infra_directory")
def test_start_calls_start_infra_with_directory(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_start_infra: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = env_content

    start(directory=directory)

    assert mock_start_infra.call_count == 1
    assert mock_start_infra.call_args == ((directory,), {})


@mock.patch("deepfellow.infra.start.start_infra")
@mock.patch("deepfellow.infra.start.echo.info")
@mock.patch("deepfellow.infra.start.read_env_file_to_dict")
@mock.patch("deepfellow.infra.start.check_infra_directory")
def test_echo_prints_starting_message(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_start_infra: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = env_content

    start(directory=directory)

    assert mock_echo.call_args_list[0] == mock.call("Starting DeepFellow Infra")


@mock.patch("deepfellow.infra.start.start_infra")
@mock.patch("deepfellow.infra.start.echo.info")
@mock.patch("deepfellow.infra.start.read_env_file_to_dict")
@mock.patch("deepfellow.infra.start.check_infra_directory")
def test_echo_prints_port(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_start_infra: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = env_content

    start(directory=directory)

    assert mock_echo.call_args_list[1] == mock.call(
        f"DeepFellow Infra started on http://localhost:{env_content['df_infra_port']}"
    )
