# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

import os
import stat
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.cli.utils.secret_files import tighten_secret_files

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")


@posix_only
@mock.patch("deepfellow.cli.utils.secret_files.get_secret_files")
def test_tighten_secret_files_restricts_world_readable_file(mock_files: Mock, tmp_path: Path) -> None:
    secret = tmp_path / "secrets"
    secret.write_text("DF_USER_TOKEN=x")
    secret.chmod(0o644)
    mock_files.return_value = [secret]

    changed = tighten_secret_files()

    assert changed == [secret]
    assert stat.S_IMODE(secret.stat().st_mode) == 0o600


@posix_only
@mock.patch("deepfellow.cli.utils.secret_files.get_secret_files")
def test_tighten_secret_files_skips_already_owner_only_file(mock_files: Mock, tmp_path: Path) -> None:
    secret = tmp_path / "secrets"
    secret.write_text("x")
    secret.chmod(0o600)
    mock_files.return_value = [secret]

    changed = tighten_secret_files()

    assert changed == []


@posix_only
@mock.patch("deepfellow.cli.utils.secret_files.get_secret_files")
def test_tighten_secret_files_skips_missing_file(mock_files: Mock, tmp_path: Path) -> None:
    mock_files.return_value = [tmp_path / "missing"]

    changed = tighten_secret_files()

    assert changed == []


@posix_only
@mock.patch("deepfellow.cli.utils.secret_files.get_secret_files")
def test_tighten_secret_files_skips_symlink(mock_files: Mock, tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("x")
    target.chmod(0o644)
    link = tmp_path / "link"
    link.symlink_to(target)
    mock_files.return_value = [link]

    changed = tighten_secret_files()

    assert changed == []
    assert stat.S_IMODE(target.stat().st_mode) == 0o644


@mock.patch("deepfellow.cli.utils.secret_files.os.name", "nt")
@mock.patch("deepfellow.cli.utils.secret_files.get_secret_files")
def test_tighten_secret_files_does_nothing_on_windows(mock_files: Mock) -> None:
    changed = tighten_secret_files()

    assert changed == []
    assert mock_files.call_count == 0
