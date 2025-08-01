"""System utils."""

import shutil
import subprocess
from pathlib import Path

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug


def run(
    command: str, cwd: Path | str | None = None, poetry: bool = False, raises: Exception | None = None
) -> str | None:
    """Run subbrocess command.

    Args:
        command: command to run
        cwd: directory to run from
        poetry: should we call from poetry
        raises: exception to be raised if failed
    """
    cmd = command
    if poetry:
        cmd = f"poetry run {cmd}"

    try:
        process = subprocess.run(cmd, cwd=cwd, shell=True, check=True, text=True)
    except subprocess.CalledProcessError as exc_info:
        echo.debug(f"Failed to run command {command} {cwd=} {poetry=}")
        if raises is not None:
            raise raises from exc_info

        reraise_if_debug(exc_info)
    else:
        return process.stdout


def is_command_available(command: str) -> bool:
    """Check if command is accessible in the system."""
    return shutil.which(command) is not None
