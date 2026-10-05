# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from datetime import datetime, timezone

from deepfellow.server.utils.time import is_within_shift_window


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 1, hour, minute, tzinfo=timezone.utc)


def test_is_within_shift_window_overnight_window_is_within_after_start():
    assert is_within_shift_window("22:00", "06:00", now=_at(23, 30)) is True


def test_is_within_shift_window_overnight_window_is_within_before_stop():
    assert is_within_shift_window("22:00", "06:00", now=_at(2, 0)) is True


def test_is_within_shift_window_overnight_window_is_outside_between_stop_and_start():
    assert is_within_shift_window("22:00", "06:00", now=_at(14, 50)) is False


def test_is_within_shift_window_overnight_window_exactly_at_start_is_within():
    assert is_within_shift_window("22:00", "06:00", now=_at(22, 0)) is True


def test_is_within_shift_window_overnight_window_exactly_at_stop_is_outside():
    assert is_within_shift_window("22:00", "06:00", now=_at(6, 0)) is False


def test_is_within_shift_window_same_day_window_is_within():
    assert is_within_shift_window("08:00", "17:00", now=_at(12, 0)) is True


def test_is_within_shift_window_same_day_window_is_outside_before_start():
    assert is_within_shift_window("08:00", "17:00", now=_at(7, 59)) is False


def test_is_within_shift_window_same_day_window_is_outside_after_stop():
    assert is_within_shift_window("08:00", "17:00", now=_at(17, 0)) is False


def test_is_within_shift_window_defaults_to_current_time_when_now_not_given():
    # Just verify it runs without a `now` argument and returns a bool - doesn't assert a specific
    # result, since that would depend on when the test happens to run.
    result = is_within_shift_window("00:00", "23:59")
    assert isinstance(result, bool)
