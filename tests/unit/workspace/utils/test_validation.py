# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path

import pytest
import typer

from deepfellow.workspace.utils.validation import check_workspace_directory


def test_check_workspace_directory_with_compose_file_passes(tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    check_workspace_directory(tmp_path)


def test_check_workspace_directory_without_compose_file_exits(tmp_path: Path) -> None:
    with pytest.raises(typer.Exit):
        check_workspace_directory(tmp_path)


def test_check_workspace_directory_missing_directory_exits(tmp_path: Path) -> None:
    with pytest.raises(typer.Exit):
        check_workspace_directory(tmp_path / "nope")
