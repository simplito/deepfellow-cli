# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

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
@mock.patch("deepfellow.infra.start.assert_docker")
@mock.patch("deepfellow.infra.start.check_infra_directory")
def test_start_calls_check_infra_directory(
    mock_check: Mock,
    mock_assert_docker: Mock,
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
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.start.start_infra")
@mock.patch("deepfellow.infra.start.echo.info")
@mock.patch("deepfellow.infra.start.read_env_file_to_dict")
@mock.patch("deepfellow.infra.start.assert_docker")
@mock.patch("deepfellow.infra.start.check_infra_directory")
def test_start_calls_start_infra_with_directory(
    mock_check: Mock,
    mock_assert_docker: Mock,
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
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.start.start_infra")
@mock.patch("deepfellow.infra.start.echo.info")
@mock.patch("deepfellow.infra.start.read_env_file_to_dict")
@mock.patch("deepfellow.infra.start.assert_docker")
@mock.patch("deepfellow.infra.start.check_infra_directory")
def test_echo_prints_starting_message(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_start_infra: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = env_content

    start(directory=directory)

    assert mock_echo.call_args_list[0] == mock.call("Starting DeepFellow Infra")
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.start.start_infra")
@mock.patch("deepfellow.infra.start.echo.info")
@mock.patch("deepfellow.infra.start.read_env_file_to_dict")
@mock.patch("deepfellow.infra.start.assert_docker")
@mock.patch("deepfellow.infra.start.check_infra_directory")
def test_echo_prints_port(
    mock_check: Mock,
    mock_assert_docker: Mock,
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
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.start.start_infra")
@mock.patch("deepfellow.infra.start.echo.info")
@mock.patch("deepfellow.infra.start.read_env_file_to_dict")
@mock.patch("deepfellow.infra.start.assert_docker")
@mock.patch("deepfellow.infra.start.check_infra_directory")
def test_echo_prints_bind_address_url(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_start_infra: Mock,
    directory: Path,
    env_content: dict,
) -> None:
    mock_read.return_value = {**env_content, "df_infra_bind_address": "127.0.0.1"}

    start(directory=directory)

    assert mock_echo.call_args_list[1] == mock.call(
        f"DeepFellow Infra started on http://127.0.0.1:{env_content['df_infra_port']}"
    )
