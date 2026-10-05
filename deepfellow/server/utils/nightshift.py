# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Applying a Nightshift mode/schedule change - shared by `nightshift mode`, `nightshift schedule` and `env set`."""

from collections.abc import Mapping
from pathlib import Path

import typer

from deepfellow.common.defaults import NightshiftModeChoice
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.validation import validate_distinct_hours, validate_hhmm
from deepfellow.server.utils.docker import assert_nightshift_installed, reconcile_nightshift_running_state
from deepfellow.server.utils.systemd import reconcile_nightshift_schedule, remove_nightshift_timers


def validate_nightshift_schedule(mode: str, start: str, stop: str) -> None:
    """Reject a mode/hours combination the systemd timers can't be generated from.

    An empty hour is not an error here: shift mode without hours is allowed (see
    `apply_nightshift_schedule`). The hours are only looked at in `shift` mode - nothing is
    generated from them otherwise, so a stale or malformed stored value must not block switching
    away from it.
    """
    try:
        NightshiftModeChoice(mode)
    except ValueError:
        allowed = ", ".join(choice.value for choice in NightshiftModeChoice)
        raise typer.BadParameter(f"Invalid Nightshift mode '{mode}' - must be one of: {allowed}.") from None
    if mode != NightshiftModeChoice.shift.value:
        return
    if start:
        validate_hhmm(start)
    if stop:
        validate_hhmm(stop)
    if start and stop:
        validate_distinct_hours(start, stop)


def apply_nightshift_schedule(
    directory: Path, mode: str, start: str, stop: str, env_updates: Mapping[str, str]
) -> None:
    """Bring the systemd timers, `.env` and the worker's running state in line with a new mode/schedule.

    `.env` stays the source of truth and the timers are derived from it, so a change to any of
    `DF_NIGHTSHIFT_MODE`/`START`/`STOP` has to regenerate them - whichever command made it. The
    timers go first, so a host that can't support them fails before `.env` is touched. The
    worker is then only started or stopped if its state no longer matches (never blindly
    restarted, which would interrupt a running job).

    Args:
        directory: The server install directory.
        mode: The resulting mode (`always` or `shift`).
        start: The resulting start hour, "HH:MM" - empty if unset.
        stop: The resulting stop hour, "HH:MM" - empty if unset.
        env_updates: The `.env` keys to write for this change.
    """
    assert_nightshift_installed(directory)
    validate_nightshift_schedule(mode, start, stop)
    if mode == NightshiftModeChoice.shift.value and not (start and stop):
        # Timers left over from an earlier, complete schedule would keep firing at the old hours.
        remove_nightshift_timers(directory)
        echo.warning(
            "Shift mode without both start and stop hours: there are no systemd timers (any existing ones were "
            "removed), so the worker behaves as always-on until both hours are set "
            "(`deepfellow server nightshift schedule`)."
        )
    else:
        reconcile_nightshift_schedule(directory, mode, start, stop)

    for key, value in env_updates.items():
        env_set(directory / ".env", key, value)

    reconcile_nightshift_running_state(directory)
