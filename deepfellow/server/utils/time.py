"""Time related utils."""

from datetime import datetime

from tzlocal.unix import get_localzone


def datetime_to_str(value: float) -> str:
    """Convert float representing datetime to a localized date string."""
    return str(datetime.fromtimestamp(value, tz=get_localzone()))
