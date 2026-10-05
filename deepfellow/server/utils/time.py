# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Time related utils."""

from datetime import datetime, time

from tzlocal.unix import get_localzone


def datetime_to_str(value: float) -> str:
    """Convert float representing datetime to a localized date string."""
    return str(datetime.fromtimestamp(value, tz=get_localzone()))


def _parse_hhmm(value: str) -> time:
    """Parse an "HH:MM" string into a `time` - raises ValueError on anything else."""
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def is_within_shift_window(start: str, stop: str, now: datetime | None = None) -> bool:
    """Whether the current (or given) local time falls within a shift-mode [start, stop) window.

    Handles an overnight window (`start` after `stop`, e.g. "22:00"-"06:00", the common case for
    Nightshift) by treating it as spanning midnight: `now` counts as "within" if it's at or after
    `start` OR before `stop`. For a same-day window (`start` before `stop`), it's the plain
    `start <= now < stop` range.

    Args:
        start: Shift start hour, "HH:MM", host timezone.
        stop: Shift stop hour, "HH:MM", host timezone.
        now: The instant to check - defaults to the current local time (`tzlocal`, matching the
            rest of Nightshift's scheduling, which runs in the host's timezone).
    """
    current = (now or datetime.now(get_localzone())).time()
    start_time = _parse_hhmm(start)
    stop_time = _parse_hhmm(stop)
    if start_time <= stop_time:
        return start_time <= current < stop_time
    return current >= start_time or current < stop_time
