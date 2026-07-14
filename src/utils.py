"""
Shared utility functions across the app.
"""

from datetime import datetime, timezone, timedelta


def time_filter_to_ts(time_filter: str) -> int:
    """Convert a time filter label to a UTC Unix timestamp for the start of that period."""
    now = datetime.now(timezone.utc)
    if time_filter == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_filter == "this_week":
        start = now - timedelta(days=7)
    else:  # this_month
        start = now - timedelta(days=30)
    return int(start.timestamp())


def time_filter_to_iso(time_filter: str) -> str:
    """Convert a time filter label to a UTC ISO 8601 string for the start of that period."""
    ts = time_filter_to_ts(time_filter)
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "") + "Z"
