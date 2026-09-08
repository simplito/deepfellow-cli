# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Persisted progress state for `suite install`, enabling `--resume` after a partial failure."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from deepfellow.common.defaults import DF_SUITE_INSTALL_STATE_FILE
from deepfellow.common.echo import echo


@dataclass
class SuiteInstallState:
    """Which suite-install steps have completed so far, and any output a later step needs.

    `workspace` holds the workspace-creation step's result (organization/project/api_key) once
    that step succeeds - its API key can't be retrieved again after creation, so a `--resume` run
    that reaches a later step must reuse this instead of re-creating the workspace.

    `admin` holds the {"name", "email", "password"} resolved for this run (from
    --admin-*/env vars, or interactively prompted) - persisted so a later `--resume` run can reuse
    them instead of prompting again, while an explicit --admin-* flag on that later run still wins
    over the persisted value (see `resolve_admin_kwargs`).

    `infra_config`/`server_config` hold infra's and server's fully-resolved `InstallConfig` (see
    `_infra_config_to_dict()`/`_server_config_to_dict()` in `suite/utils/install.py`) once each
    one's own ask-phase step succeeds - persisted so a later `--resume` run's apply-phase steps
    reuse them instead of re-resolving (re-prompting), and so a self-healing repair of a damaged
    directory reapplies the exact same configuration rather than resolving a fresh one. A state
    file written before these fields existed simply has them as `None` - `load()` doesn't need to
    special-case that, since a `None` config is indistinguishable from "not yet resolved" and the
    corresponding step just runs (and re-prompts) once more, exactly as if it were a fresh install.

    No schema version field: this file only ever lives for the lifetime of one failed-and-resumed
    `suite install` attempt - `delete()` removes it on any full success, and `--resume` is never
    meant to reattach to a run from a different CLI version. A schema-shape change simply isn't a
    concern this file needs to defend against.
    """

    completed_steps: list[str] = field(default_factory=list)
    workspace: dict[str, Any] | None = None
    admin: dict[str, str] | None = None
    infra_config: dict[str, Any] | None = None
    server_config: dict[str, Any] | None = None


def load(state_file: Path = DF_SUITE_INSTALL_STATE_FILE) -> SuiteInstallState | None:
    """Load a previously persisted suite-install state, if any.

    Args:
        state_file: Path to the state file.

    Returns:
        The persisted state, or None if the file doesn't exist, or exists but can't be read or
        parsed (e.g. corrupted by a crash mid-write) - in which case a warning is echoed, since
        this function is always called at the start of `install()` regardless of `--resume`, and
        silently treating a broken file as "nothing to resume" would leave no indication anything
        was wrong.
    """
    if not state_file.is_file():
        return None

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        echo.warning(f"Suite install state file {state_file} exists but could not be read ({exc}); ignoring it.")
        return None

    if not isinstance(data, dict):
        echo.warning(f"Suite install state file {state_file} exists but its content is not valid; ignoring it.")
        return None

    return SuiteInstallState(
        # `or []`, not `.get("completed_steps", [])`'s default alone - a key present with an
        # explicit `null` value (as opposed to being absent) makes `.get()` return None, not the
        # default, and `list(None)` raises an unhandled TypeError.
        completed_steps=list(data.get("completed_steps") or []),
        workspace=data.get("workspace"),
        admin=data.get("admin"),
        infra_config=data.get("infra_config"),
        server_config=data.get("server_config"),
    )


def save(install_state: SuiteInstallState, state_file: Path = DF_SUITE_INSTALL_STATE_FILE) -> None:
    """Persist suite-install state, overwriting any previous content.

    Writes to a temp file in the same directory and atomically renames it into place (`Path.replace`)
    rather than truncating `state_file` directly - a crash mid-write (OOM kill, Ctrl+C, power loss)
    would otherwise leave a partially-written, corrupted JSON file behind, which `load()` then
    treats as unreadable, silently losing whatever progress - including a one-time, unrecoverable
    workspace API key - the file it just clobbered was holding.

    Args:
        install_state: The state to persist.
        state_file: Path to the state file.
    """
    state_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(dir=state_file.parent, prefix=f".{state_file.name}.", suffix=".tmp")
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(json.dumps(asdict(install_state), indent=2))
        tmp_path.replace(state_file)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def delete(state_file: Path = DF_SUITE_INSTALL_STATE_FILE) -> None:
    """Remove the persisted suite-install state, if present.

    Args:
        state_file: Path to the state file.
    """
    state_file.unlink(missing_ok=True)
