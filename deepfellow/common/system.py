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

import typer

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.state import state


def run(
    command: str | list[str],
    cwd: Path | str | None = None,
    raises: type[Exception] | None = None,
    quiet: bool = False,
    shell: bool = False,
    check: bool = True,
    **kwargs: Any,
) -> str | None:
    """Run subbrocess command.

    Calls `subprocess.run` with a preset arguments.

    Raising exception logic:
    - A failure is either `subprocess.CalledProcessError` (command ran, exited non-zero) or an
      `OSError` (command never started - missing executable, invalid `cwd`, permission denied).
      Both are handled the same way.
    - If a custom exception is provided in `raises`, it is raised for either failure mode.
    - Otherwise, `--debug` reraises the original exception; without `--debug`, `run` exits with
      code 1 after printing (for `CalledProcessError`) the filtered stderr, or (for `OSError`)
      the error itself.
    - `run` only returns `None` on success when the caller didn't capture output (no
      `capture_output=True` / `stdout=...`) - a failure never produces a `None` return, it always
      raises. Do not use `run(...) is None` to detect failure; use `raises=` and catch it instead.

    Sample usage:
    ```
    try:
        run(["some", "command"], raises=SomeError)
    except SomeError:
        echo.error("some error")
    ```

    Args:
        command: command to run
        cwd: directory to run from
        raises: exception to be raised if failed
        quiet: mute stdout and stderr
        shell: should subrocess run as shell command
        check: should subprocess raise an issue if failed
        kwargs: pass additional kwargs to subrocess.run

    Returns:
        Process's `stdout`, or `None` if the caller didn't capture it.

    Raises:
        - Custom exception, if it is provided in the `raises` kwarg
        - subprocess.CalledProcessError or OSError if in debug mode
    """
    cmd = command
    clean_env = os.environ.copy()
    clean_env.pop("VIRTUAL_ENV", None)

    if quiet and kwargs.get("capture_output"):
        raise SystemError("ERROR: If quiet then not capture_output")

    if quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.PIPE

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
        echo.debug(f"Failed to run command {command} {cwd=}")
        if raises is not None:
            raise raises(exc_info.stderr) from exc_info

        if exc_info.stderr:
            error_lines = [
                line
                for line in exc_info.stderr.splitlines()
                if "level=warning" not in line and "level=info" not in line
            ]
            if error_lines:
                echo.error("\n".join(error_lines).strip())
        reraise_if_debug(exc_info)
    except OSError as exc_info:
        echo.debug(f"Failed to start command {command} {cwd=}: {exc_info}")
        if raises is not None:
            raise raises(str(exc_info)) from exc_info

        echo.error(str(exc_info))
        reraise_if_debug(exc_info)
    else:
        return process.stdout


def rmtree(path: Path) -> None:
    """Remove a directory tree, falling back to ``sudo rm -rf`` on PermissionError.

    Docker containers create root-owned files the CLI user cannot remove.
    On failure, prompts the user to retry with sudo (auto-confirmed with --yes).
    """
    try:
        shutil.rmtree(path)
    except PermissionError:
        pass
    else:
        return

    echo.warning(f"Cannot remove {path.as_posix()}: permission denied (Docker-owned files).")
    if state.yes or echo.confirm("Retry with sudo?", default=True):
        if run(["sudo", "-n", "rm", "-rf", path.as_posix()]) is None:
            echo.error(f"sudo rm -rf failed. Remove manually: sudo rm -rf {path.as_posix()}")
            raise typer.Exit(1)
    else:
        echo.error(f"Remove manually: sudo rm -rf {path.as_posix()}")
        raise typer.Exit(1)


def is_command_available(command: str) -> bool:
    """Check if command is accessible in the system."""
    return shutil.which(command) is not None


def check_service_directory(directory: Path, service_name: str) -> None:
    """Check if service directory exist."""
    if not directory.is_dir():
        echo.error(f"Create Deepfellow {service_name} first.")
        raise typer.Exit(1)
