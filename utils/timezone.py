from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DISPLAY_FORMAT = '%Y-%m-%d %H:%M:%S'

try:
    BAKU_TZ = ZoneInfo('Asia/Baku')
except ZoneInfoNotFoundError:  # pragma: no cover - depends on system tzdata
    BAKU_TZ = timezone(timedelta(hours=4))


def parse_utc_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_to_baku(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
    else:
        dt = parse_utc_datetime(value)
    if dt is None:
        return None
    return dt.astimezone(BAKU_TZ)


def format_baku(value: str | datetime | None) -> str:
    dt = utc_to_baku(value)
    if dt is None:
        return '—'
    return dt.strftime(DISPLAY_FORMAT)
