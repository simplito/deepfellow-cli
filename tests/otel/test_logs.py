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

import pytest
import typer

from deepfellow.otel.logs import logs


@mock.patch("deepfellow.otel.logs.run")
@mock.patch("deepfellow.otel.logs.echo")
@mock.patch("deepfellow.otel.logs.is_service_running", return_value=True)
@mock.patch("deepfellow.otel.logs.Path.exists", return_value=True)
def test_logs_tails_collector_with_defaults(
    mock_exists: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
):
    logs(directory=directory, follow=False, tail=20)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(
        ["docker", "compose", "logs", "otel-collector", "--tail", "20"], cwd=directory
    )


@mock.patch("deepfellow.otel.logs.run")
@mock.patch("deepfellow.otel.logs.echo")
@mock.patch("deepfellow.otel.logs.is_service_running", return_value=True)
@mock.patch("deepfellow.otel.logs.Path.exists", return_value=True)
def test_logs_appends_follow_flag(
    mock_exists: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
):
    logs(directory=directory, follow=True, tail=20)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(
        ["docker", "compose", "logs", "otel-collector", "-f", "--tail", "20"], cwd=directory
    )


@mock.patch("deepfellow.otel.logs.run")
@mock.patch("deepfellow.otel.logs.echo")
@mock.patch("deepfellow.otel.logs.is_service_running", return_value=True)
@mock.patch("deepfellow.otel.logs.Path.exists", return_value=True)
def test_logs_uses_custom_tail(
    mock_exists: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
):
    logs(directory=directory, follow=False, tail=5)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(
        ["docker", "compose", "logs", "otel-collector", "--tail", "5"], cwd=directory
    )


@mock.patch("deepfellow.otel.logs.run")
@mock.patch("deepfellow.otel.logs.echo")
@mock.patch("deepfellow.otel.logs.is_service_running", return_value=True)
@mock.patch("deepfellow.otel.logs.Path.exists", return_value=False)
def test_logs_exits_when_collector_not_installed(
    mock_exists: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
):
    with pytest.raises(typer.Exit):
        logs(directory=directory, follow=False, tail=20)

    assert mock_echo.error.call_count == 1
    assert mock_run.call_count == 0


@mock.patch("deepfellow.otel.logs.run")
@mock.patch("deepfellow.otel.logs.echo")
@mock.patch("deepfellow.otel.logs.is_service_running", return_value=False)
@mock.patch("deepfellow.otel.logs.Path.exists", return_value=True)
def test_logs_exits_when_collector_not_running(
    mock_exists: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_run: mock.MagicMock,
    directory: Path,
):
    with pytest.raises(typer.Exit):
        logs(directory=directory, follow=False, tail=20)

    assert mock_is_service_running.call_count == 1
    assert mock_is_service_running.call_args == mock.call("otel-collector", directory)
    assert mock_echo.error.call_count == 1
    assert mock_run.call_count == 0
