"""
Timezone utilities for AutoTrade AI
Ensures all times are in Indian Standard Time (IST)
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Indian Standard Time
IST = ZoneInfo('Asia/Kolkata')

def now_ist() -> datetime:
    """Get current time in IST"""
    return datetime.now(IST)

def utc_to_ist(dt: datetime) -> datetime:
    """Convert UTC datetime to IST"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def ist_to_utc(dt: datetime) -> datetime:
    """Convert IST datetime to UTC"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(timezone.utc)

def format_ist(dt: datetime = None, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """Format datetime in IST"""
    if dt is None:
        dt = now_ist()
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    else:
        dt = dt.astimezone(IST)
    return dt.strftime(fmt) + ' IST'

def today_ist() -> datetime:
    """Get today's date in IST (midnight)"""
    return now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
