"""In-memory screenshot storage for the RAM-only monitor flow."""

SCREENSHOT_STORE: dict[str, bytes] = {}


def put_screenshot(filename: str, data: bytes) -> None:
    """Store screenshot bytes in RAM only."""
    SCREENSHOT_STORE[filename] = data


def get_screenshot(filename: str) -> bytes | None:
    """Return screenshot bytes from RAM, if present."""
    return SCREENSHOT_STORE.get(filename)
