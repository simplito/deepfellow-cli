# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared resolver for config-driven CLI self-management commands."""

import shlex
from collections.abc import Callable

from deepfellow.common.config import read_env_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.state import state

PACKAGE_NAME = "deepfellow-cli"


def resolve_cli_command(config_key: str, detect: Callable[[], list[str] | None]) -> list[str] | None:
    """Resolve a CLI self-management command (update/uninstall).

    Resolution order:
        1. Read ``config_key`` from the CLI config file and parse it with ``shlex.split``.
        2. If absent (or invalid), fall back to runtime package-manager detection.
        3. Self-heal: when detection succeeds, persist the resolved command back to config
           under ``config_key`` so subsequent runs read it directly.
        4. Return ``None`` when neither yields a command; the caller prints manual instructions.

    Args:
        config_key: Config key holding the stored command (e.g. ``DF_UPDATE_COMMAND``).
        detect: Callback performing runtime package-manager detection.

    Returns:
        The resolved command as an argv list, or ``None`` when it cannot be resolved.
    """
    stored = _read_stored_command(config_key)
    if stored is not None:
        return stored

    detected = detect()
    if detected is not None:
        _persist_command(config_key, detected)
    return detected


def _read_stored_command(config_key: str) -> list[str] | None:
    """Read and parse a stored command from the CLI config file."""
    if not state.cli_config_file.is_file():
        return None

    try:
        envs = read_env_file(state.cli_config_file)
    except FileNotFoundError:
        return None

    cmd_str = envs.get(config_key, "").strip()
    if not cmd_str:
        return None

    try:
        return shlex.split(cmd_str)
    except ValueError:
        echo.warning(f"Invalid {config_key} in config, falling back to auto-detection.")
        return None


def _persist_command(config_key: str, cmd: list[str]) -> None:
    """Write the resolved command back to config so subsequent runs use it."""
    env_set(
        state.cli_config_file,
        config_key,
        shlex.join(cmd),
        should_raise=False,
        quiet=True,
        docker_note=False,
    )
