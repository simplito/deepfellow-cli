"""Git commands."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import GitError, reraise_if_debug


@dataclass
class Git:
    repository: str

    def clone(self, branch: str | None = None, tag: str | None = None, directory: Path = Path()) -> None:
        """Clone repository.

        Args:
            branch: branch to clone from. If None import from default branch (default: None)
            tag: Use tag to clone (default: None)
            directory: Directory to clone to, by default current directory (default: ".")
        """
        if branch is not None and tag is not None and branch != tag:
            raise GitError("branch and tag can't be provided at the same time.")

        point = branch or tag
        cmd_point = "" if point is None else f"-b {point} --single-branch"
        cmd = f"git clone  --depth 1 {cmd_point} {self.repository} {directory}"
        echo.debug(cmd)
        try:
            subprocess.run(cmd, shell=True, check=True, text=True)
        except subprocess.CalledProcessError as exc_info:
            echo.error(f"Failed to clone from {self.repository} {branch=} {tag=}")
            reraise_if_debug(exc_info)
