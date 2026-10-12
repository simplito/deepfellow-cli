# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""File helpers."""

import os
import tempfile
from pathlib import Path


def write_private_file(path: Path, content: str) -> None:
    """Write `content` to `path` readable and writable by the owner only (0600), regardless of umask.

    Writes to a temp file in the same directory (`tempfile.mkstemp` creates it with 0600) and atomically
    renames it over `path`, so an existing file with broader permissions ends up narrowed too and a crash
    mid-write (OOM kill, Ctrl+C, power loss) cannot leave a truncated file. On Windows POSIX permission bits
    have no effect, which is harmless.

    Args:
        path: Destination file.
        content: Text to write.
    """
    fd, tmp_path_str = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(content)
        tmp_path.replace(path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
