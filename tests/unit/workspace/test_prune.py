# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.workspace.prune import prune


@mock.patch("deepfellow.workspace.prune.rmtree")
@mock.patch("deepfellow.workspace.prune.remove_webhook")
@mock.patch("deepfellow.workspace.prune.echo")
@mock.patch("deepfellow.workspace.prune.run")
@mock.patch("deepfellow.workspace.prune.assert_docker")
def test_prune_removes_webhook_stack_with_volumes_and_directory(
    mock_assert_docker: Mock, mock_run: Mock, mock_echo: Mock, mock_webhook: Mock, mock_rmtree: Mock, tmp_path: Path
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")
    (tmp_path / ".env").write_text("PUBLIC_URL=https://ws.example.com\n")

    prune(directory=tmp_path)

    assert mock_webhook.call_args == mock.call({"PUBLIC_URL": "https://ws.example.com"})
    assert mock_run.call_args == mock.call(
        ["docker", "compose", "down", "-v", "--remove-orphans"], tmp_path, quiet=True
    )
    assert mock_rmtree.call_args == mock.call(tmp_path)
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.workspace.prune.rmtree")
@mock.patch("deepfellow.workspace.prune.remove_webhook")
@mock.patch("deepfellow.workspace.prune.echo")
@mock.patch("deepfellow.workspace.prune.run")
@mock.patch("deepfellow.workspace.prune.assert_docker")
def test_prune_without_directory_reports_already_pruned(
    mock_assert_docker: Mock, mock_run: Mock, mock_echo: Mock, mock_webhook: Mock, mock_rmtree: Mock, tmp_path: Path
) -> None:
    prune(directory=tmp_path / "missing")

    assert mock_run.call_count == 0
    assert mock_webhook.call_count == 0
    assert mock_rmtree.call_count == 0
    assert "already pruned" in mock_echo.info.call_args.args[0]


@mock.patch("deepfellow.workspace.prune.rmtree")
@mock.patch("deepfellow.workspace.prune.remove_webhook")
@mock.patch("deepfellow.workspace.prune.echo")
@mock.patch("deepfellow.workspace.prune.run")
@mock.patch("deepfellow.workspace.prune.assert_docker")
def test_prune_directory_without_compose_file_skips_docker_and_removes_directory(
    mock_assert_docker: Mock, mock_run: Mock, mock_echo: Mock, mock_webhook: Mock, mock_rmtree: Mock, tmp_path: Path
) -> None:
    prune(directory=tmp_path)

    assert mock_assert_docker.call_count == 0
    assert mock_run.call_count == 0
    assert mock_rmtree.call_args == mock.call(tmp_path)


@mock.patch("deepfellow.workspace.prune.rmtree")
@mock.patch("deepfellow.workspace.prune.remove_webhook")
@mock.patch("deepfellow.workspace.prune.echo")
@mock.patch("deepfellow.workspace.prune.run", side_effect=typer.Exit(1))
@mock.patch("deepfellow.workspace.prune.assert_docker")
def test_prune_failed_compose_down_keeps_files_and_does_not_report_success(
    mock_assert_docker: Mock, mock_run: Mock, mock_echo: Mock, mock_webhook: Mock, mock_rmtree: Mock, tmp_path: Path
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    with pytest.raises(typer.Exit):
        prune(directory=tmp_path)

    assert mock_rmtree.call_count == 0
    assert mock_echo.success.call_count == 0
    assert mock_webhook.call_count == 0
