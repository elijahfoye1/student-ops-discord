"""Timezone-safe date/time utilities."""

from datetime import datetime, timezone
from typing import Optional, Union
from dateutil import parser as dateutil_parser
from dateutil.tz import tzlocal, gettz


# Default timezone for the user (Louisville, KY)
DEFAULT_TZ = gettz("America/Kentucky/Louisville")


def parse_iso(date_string: Optional[str]) -> Optional[datetime]:
    """
    Parse an ISO date string into a timezone-aware datetime.
    
    Returns None if the input is None or empty.
    Assumes UTC if no timezone is specified.
    """
    if not date_string:
        return None
    
    try:
        dt = dateutil_parser.isoparse(date_string)
        # If no timezone info, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def now_utc() -> datetime:
    """Get the current time in UTC."""
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    """Get the current time in the local timezone."""
    return datetime.now(DEFAULT_TZ)


def hours_until(due_at: Optional[Union[str, datetime]]) -> Optional[float]:
    """
    Calculate hours until a deadline.
    
    Returns None if due_at is None.
    Returns negative values if the deadline has passed.
    """
    if due_at is None:
        return None
    
    if isinstance(due_at, str):
        due_at = parse_iso(due_at)
    
    if due_at is None:
        return None
    
    now = now_utc()
    delta = due_at - now
    return delta.total_seconds() / 3600


def days_until(due_at: Optional[Union[str, datetime]]) -> Optional[float]:
    """Calculate days until a deadline."""
    hours = hours_until(due_at)
    if hours is None:
        return None
    return hours / 24


def format_relative(due_at: Optional[Union[str, datetime]]) -> str:
    """
    Format a deadline as a human-readable relative time.
    
    Examples: "in 6 hours", "tomorrow", "in 3 days", "overdue by 2 hours"
    """
    if due_at is None:
        return "no due date"
    
    hours = hours_until(due_at)
    if hours is None:
        return "no due date"
    
    if hours < 0:
        # Overdue
        abs_hours = abs(hours)
        if abs_hours < 1:
            return f"overdue by {int(abs_hours * 60)} minutes"
        elif abs_hours < 24:
            return f"overdue by {int(abs_hours)} hours"
        else:
            return f"overdue by {int(abs_hours / 24)} days"
    elif hours < 1:
        return f"in {int(hours * 60)} minutes"
    elif hours < 24:
        return f"in {int(hours)} hours"
    elif hours < 48:
        return "tomorrow"
    else:
        return f"in {int(hours / 24)} days"


def format_datetime(dt: Optional[Union[str, datetime]], include_time: bool = True) -> str:
    """Format a datetime for display."""
    if dt is None:
        return "N/A"
    
    if isinstance(dt, str):
        dt = parse_iso(dt)
    
    if dt is None:
        return "N/A"
    
    # Convert to local timezone
    local_dt = dt.astimezone(DEFAULT_TZ)
    
    if include_time:
        return local_dt.strftime("%b %d, %Y at %I:%M %p")
    else:
        return local_dt.strftime("%b %d, %Y")


def is_today(dt: Optional[Union[str, datetime]]) -> bool:
    """Check if a datetime is today (in local timezone)."""
    if dt is None:
        return False
    
    if isinstance(dt, str):
        dt = parse_iso(dt)
    
    if dt is None:
        return False
    
    local_dt = dt.astimezone(DEFAULT_TZ)
    today = now_local().date()
    return local_dt.date() == today


def is_tomorrow(dt: Optional[Union[str, datetime]]) -> bool:
    """Check if a datetime is tomorrow (in local timezone)."""
    if dt is None:
        return False
    
    if isinstance(dt, str):
        dt = parse_iso(dt)
    
    if dt is None:
        return False
    
    local_dt = dt.astimezone(DEFAULT_TZ)
    from datetime import timedelta
    tomorrow = (now_local() + timedelta(days=1)).date()
    return local_dt.date() == tomorrow


def is_this_week(dt: Optional[Union[str, datetime]]) -> bool:
    """Check if a datetime is within the next 7 days."""
    hours = hours_until(dt)
    if hours is None:
        return False
    return 0 <= hours <= 168  # 7 days * 24 hours
