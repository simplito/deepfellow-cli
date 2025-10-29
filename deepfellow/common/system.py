"""System utils."""

import os
import shutil
import subprocess
from pathlib import Path

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug


def run(
    command: str, cwd: Path | str | None = None, uv: bool = False, raises: Exception | None = None, **kwargs
) -> str | None:
    """Run subbrocess command.

    Args:
        command: command to run
        cwd: directory to run from
        uv: should we call from uv
        raises: exception to be raised if failed
        kwargs: pass additional kwargs to subrocess.run
    """
    cmd = command
    if uv:
        cmd = f"uv run {cmd}"

    clean_env = os.environ.copy()
    clean_env.pop("VIRTUAL_ENV", None)

    try:
        process = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            check=True,
            text=True,
            env=clean_env,
            **kwargs,
        )
    except subprocess.CalledProcessError as exc_info:
        echo.debug(f"Failed to run command {command} {cwd=} {uv=}")
        if raises is not None:
            raise raises from exc_info

        reraise_if_debug(exc_info)
    else:
        return process.stdout


def is_command_available(command: str) -> bool:
    """Check if command is accessible in the system."""
    return shutil.which(command) is not None
