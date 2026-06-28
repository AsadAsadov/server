"""In-memory screenshot storage for the RAM-only monitor flow."""
from datetime import datetime, timedelta

SCREENSHOT_STORE: dict[str, bytes] = {}
SCREENSHOT_CREATED_AT: dict[str, datetime] = {}


def put_screenshot(filename: str, data: bytes, created_at: datetime | None = None) -> None:
    """Store screenshot bytes in RAM only."""
    SCREENSHOT_STORE[filename] = data
    SCREENSHOT_CREATED_AT[filename] = created_at or datetime.utcnow()


def get_screenshot(filename: str) -> bytes | None:
    """Return screenshot bytes from RAM, if present."""
    return SCREENSHOT_STORE.get(filename)


def cleanup_ram_store(keep_minutes: int) -> None:
    """Remove RAM-only image bytes older than the gallery retention window."""
    limit = datetime.utcnow() - timedelta(minutes=keep_minutes)
    for filename, created_at in list(SCREENSHOT_CREATED_AT.items()):
        if created_at < limit:
            SCREENSHOT_STORE.pop(filename, None)
            SCREENSHOT_CREATED_AT.pop(filename, None)
