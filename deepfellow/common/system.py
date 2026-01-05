# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""System utils."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug


def run(
    command: str | list[str],
    cwd: Path | str | None = None,
    uv: bool = False,
    raises: type[Exception] | None = None,
    quiet: bool = False,
    shell: bool = False,
    check: bool = True,
    **kwargs: Any,
) -> str | None:
    """Run subbrocess command.

    Calls `subprocess.run` with a preset arguments.

    Raising exception logic:
    - By default, `subprocess.CalledProcessError` is suppressed - `run` would return `None` if raised.
    - If a custom exception is provided in `raises`, it will be raised.
    - If `--debug` is used and `raises` is `None`, `subprocess.CalledProcessError` is reraised.

    Sample usage:
    ```
    if run(["some", "command"]) is None:
        echo.error("some error")

    try:
        run(["some", "command"], raises=SomeError)
    except SomeError:
        echo.error("some error")
    ```

    Args:
        command: command to run
        cwd: directory to run from
        uv: should we call from uv
        raises: exception to be raised if failed
        quiet: mute stdout and stderr
        shell: should subrocess run as shell command
        check: should subprocess raise an issue if failed
        kwargs: pass additional kwargs to subrocess.run

    Returns:
        Process's `stdout` or `None` if error.

    Raises:
        - Custom exception, if it is provided in the `raises` kwarg
        - subprocess.CalledProcessError if in debug mode
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
            shell=shell,
            check=check,
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
