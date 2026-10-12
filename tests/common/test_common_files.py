# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

import os
import stat
import sys
from pathlib import Path
from unittest import mock

import pytest

from deepfellow.common.files import write_private_file


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits are not enforced on Windows")
@pytest.mark.parametrize("umask", [0o022, 0o000])
def test_write_private_file_new_file_has_owner_only_permissions(tmp_path: Path, umask: int) -> None:
    target = tmp_path / "secret"
    old_umask = os.umask(umask)

    try:
        write_private_file(target, "value")
    finally:
        os.umask(old_umask)

    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert target.read_text() == "value"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits are not enforced on Windows")
def test_write_private_file_overwrite_narrows_existing_permissions(tmp_path: Path) -> None:
    target = tmp_path / "secret"
    target.write_text("old")
    target.chmod(0o644)

    write_private_file(target, "new")

    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert target.read_text() == "new"


def test_write_private_file_leaves_no_temp_files_behind(tmp_path: Path) -> None:
    target = tmp_path / "secret"

    write_private_file(target, "value")

    assert [p.name for p in tmp_path.iterdir()] == ["secret"]


@mock.patch.object(Path, "replace", side_effect=OSError("boom"))
def test_write_private_file_failure_keeps_original_and_removes_temp_file(
    mock_replace: mock.Mock, tmp_path: Path
) -> None:
    target = tmp_path / "secret"
    target.write_text("original")

    with pytest.raises(OSError, match="boom"):
        write_private_file(target, "new")

    assert target.read_text() == "original"
    assert [p.name for p in tmp_path.iterdir()] == ["secret"]
