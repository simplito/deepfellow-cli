"""System utils."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug


def run(
    command: str,
    cwd: Path | str | None = None,
    uv: bool = False,
    raises: type[Exception] | None = None,
    quiet: bool = False,
    **kwargs: Any,
) -> str | None:
    """Run subbrocess command.

    Args:
        command: command to run
        cwd: directory to run from
        uv: should we call from uv
        raises: exception to be raised if failed
        quiet: mute stdout and stderr
        kwargs: pass additional kwargs to subrocess.run
    """
    cmd = command
    if uv:
        cmd = f"uv run {cmd}"

    clean_env = os.environ.copy()
    clean_env.pop("VIRTUAL_ENV", None)

    if quiet and kwargs.get("capture_output"):
        raise SystemError("ERROR: If quiet then not capture_output")

    if quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL

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
            raise raises(exc_info.stderr) from exc_info

        reraise_if_debug(exc_info)
    else:
        return process.stdout

    return None


def is_command_available(command: str) -> bool:
    """Check if command is accessible in the system."""
    return shutil.which(command) is not None
