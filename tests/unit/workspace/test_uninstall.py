# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.workspace.uninstall import uninstall


@mock.patch("deepfellow.workspace.uninstall.resolve_compose_volume_name", return_value="workspace_workspace-mongo-db")
@mock.patch("deepfellow.workspace.uninstall.echo")
@mock.patch("deepfellow.workspace.uninstall.run")
@mock.patch("deepfellow.workspace.uninstall.assert_docker")
def test_uninstall_removes_containers_and_keeps_files(
    mock_assert_docker: Mock, mock_run: Mock, mock_echo: Mock, mock_volume_name: Mock, tmp_path: Path
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}\nvolumes:\n  workspace-mongo-db:\n")
    (tmp_path / ".env").write_text("APP_SECRET=x")

    uninstall(directory=tmp_path)

    assert mock_assert_docker.call_count == 1
    assert mock_run.call_args_list == [
        mock.call(["docker", "compose", "rm", "-s", "-f", "-v"], tmp_path, quiet=True),
        mock.call(["docker", "compose", "down", "--remove-orphans"], tmp_path, quiet=True),
    ]
    assert (tmp_path / ".env").is_file()
    assert (tmp_path / "compose.yaml").is_file()
    assert "workspace_workspace-mongo-db" in mock_echo.success.call_args.args[0]
    assert mock_volume_name.call_args == mock.call(tmp_path, "workspace-mongo-db")


@mock.patch("deepfellow.workspace.uninstall.echo")
@mock.patch("deepfellow.workspace.uninstall.run")
@mock.patch("deepfellow.workspace.uninstall.assert_docker")
def test_uninstall_without_directory_reports_already_uninstalled_without_docker(
    mock_assert_docker: Mock, mock_run: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    uninstall(directory=tmp_path / "missing")

    assert mock_run.call_count == 0
    assert mock_assert_docker.call_count == 0
    assert "already uninstalled" in mock_echo.info.call_args.args[0]


@mock.patch("deepfellow.workspace.uninstall.echo")
@mock.patch("deepfellow.workspace.uninstall.run")
@mock.patch("deepfellow.workspace.uninstall.assert_docker")
def test_uninstall_directory_without_compose_file_reports_already_uninstalled(
    mock_assert_docker: Mock, mock_run: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    uninstall(directory=tmp_path)

    assert mock_run.call_count == 0
    assert str(tmp_path) in mock_echo.info.call_args.args[0]


@mock.patch("deepfellow.workspace.uninstall.echo")
@mock.patch("deepfellow.workspace.uninstall.run")
@mock.patch("deepfellow.workspace.uninstall.assert_docker", side_effect=typer.Exit(1))
def test_uninstall_without_docker_exits_before_running(
    mock_assert_docker: Mock, mock_run: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    with pytest.raises(typer.Exit):
        uninstall(directory=tmp_path)

    assert mock_run.call_count == 0


@mock.patch("deepfellow.workspace.uninstall.echo")
@mock.patch("deepfellow.workspace.uninstall.run", side_effect=typer.Exit(1))
@mock.patch("deepfellow.workspace.uninstall.assert_docker")
def test_uninstall_failed_compose_rm_does_not_report_success(
    mock_assert_docker: Mock, mock_run: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    with pytest.raises(typer.Exit):
        uninstall(directory=tmp_path)

    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.workspace.uninstall.resolve_compose_volume_name", return_value=None)
@mock.patch("deepfellow.workspace.uninstall.echo")
@mock.patch("deepfellow.workspace.uninstall.run")
@mock.patch("deepfellow.workspace.uninstall.assert_docker")
def test_uninstall_unresolvable_volume_name_falls_back_to_compose_key(
    mock_assert_docker: Mock, mock_run: Mock, mock_echo: Mock, mock_volume_name: Mock, tmp_path: Path
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}\nvolumes:\n  workspace-mongo-db:\n")

    uninstall(directory=tmp_path)

    assert "Docker volume workspace-mongo-db)" in mock_echo.success.call_args.args[0]


@mock.patch("deepfellow.workspace.uninstall.resolve_compose_volume_name")
@mock.patch("deepfellow.workspace.uninstall.echo")
@mock.patch("deepfellow.workspace.uninstall.run")
@mock.patch("deepfellow.workspace.uninstall.assert_docker")
def test_uninstall_external_mongo_does_not_report_kept_data(
    mock_assert_docker: Mock, mock_run: Mock, mock_echo: Mock, mock_volume_name: Mock, tmp_path: Path
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    uninstall(directory=tmp_path)

    assert "Mongo data" not in mock_echo.success.call_args.args[0]
    assert mock_volume_name.call_count == 0
