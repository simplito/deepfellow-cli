# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Tighten permissions of secret files created by earlier CLI versions."""

import os
import stat
from pathlib import Path

from deepfellow.common.defaults import DF_INFRA_DIRECTORY
from deepfellow.common.state import state
from deepfellow.server.utils.options import get_default_server_directory

OWNER_ONLY_MODE = 0o600
GROUP_OTHER_BITS = stat.S_IRWXG | stat.S_IRWXO


def get_secret_files() -> list[Path]:
    """Return the secret files the CLI is known to create.

    Covers the CLI secrets file and the `.env` files of the default infra and server installs.
    """
    return [
        state.cli_secrets_file,
        DF_INFRA_DIRECTORY / ".env",
        get_default_server_directory() / ".env",
    ]


def tighten_secret_files() -> list[Path]:
    """Make existing secret files readable by their owner only.

    Does nothing on Windows. Skips files that do not exist, are not regular files, are not owned by
    the current user, or are already owner-only. Failures to change a single file are ignored.

    Returns:
        Paths of the files whose permissions were changed.
    """
    if os.name == "nt":
        return []

    changed: list[Path] = []
    for path in dict.fromkeys(get_secret_files()):
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                continue
            if not info.st_mode & GROUP_OTHER_BITS:
                continue
            path.chmod(OWNER_ONLY_MODE)
        except OSError:
            continue
        changed.append(path)

    return changed
