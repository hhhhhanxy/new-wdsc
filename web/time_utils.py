"""Time helpers for user-facing Beijing time display."""
from datetime import datetime, timezone, timedelta


BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
DISPLAY_FORMAT = "%Y-%m-%d %H:%M:%S"


def beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)


def beijing_now_str() -> str:
    return beijing_now().strftime(DISPLAY_FORMAT)


def format_beijing_time(value: str) -> str:
    """Normalize stored timestamps to a user-facing Beijing time string."""
    if not value:
        return ""

    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return text

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BEIJING_TZ)
    else:
        parsed = parsed.astimezone(BEIJING_TZ)
    return parsed.strftime(DISPLAY_FORMAT)
