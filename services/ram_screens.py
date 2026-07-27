"""Thread-safe in-memory screenshot storage for the RAM-only monitor flow."""
from __future__ import annotations

from datetime import datetime, timedelta
from threading import RLock
from typing import Any

SCREENSHOT_STORE: dict[str, bytes] = {}
SCREENSHOT_CREATED_AT: dict[str, datetime] = {}
SCREENSHOT_AGENT: dict[str, str] = {}
SCREENSHOT_METADATA: dict[str, dict[str, Any]] = {}
_LOCK = RLock()


def _is_last_frame(filename: str) -> bool:
    return filename.lower().endswith('_last.jpg')


def put_screenshot(
    filename: str,
    data: bytes,
    created_at: datetime | None = None,
    agent_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Store screenshot bytes and RAM-only metadata."""
    with _LOCK:
        SCREENSHOT_STORE[filename] = data
        SCREENSHOT_CREATED_AT[filename] = created_at or datetime.utcnow()
        if agent_name is not None:
            SCREENSHOT_AGENT[filename] = agent_name
        else:
            SCREENSHOT_AGENT.pop(filename, None)
        if metadata is not None:
            SCREENSHOT_METADATA[filename] = dict(metadata)
        else:
            SCREENSHOT_METADATA.pop(filename, None)


def get_screenshot(filename: str) -> bytes | None:
    """Return screenshot bytes from RAM, if present."""
    with _LOCK:
        return SCREENSHOT_STORE.get(filename)


def get_latest_image(agent_name: str) -> tuple[bytes, str, datetime, dict[str, Any] | None] | None:
    """Return latest RAM frame for an agent, falling back to its persistent *_last.jpg frame."""
    with _LOCK:
        latest: tuple[str, datetime] | None = None
        for filename, created_at in SCREENSHOT_CREATED_AT.items():
            if SCREENSHOT_AGENT.get(filename) != agent_name or filename not in SCREENSHOT_STORE:
                continue
            if latest is None or created_at > latest[1]:
                latest = (filename, created_at)

        last_filename = f'{agent_name}_last.jpg'
        last_created_at = SCREENSHOT_CREATED_AT.get(last_filename)
        if last_filename in SCREENSHOT_STORE and last_created_at is not None:
            if latest is None or last_created_at > latest[1]:
                latest = (last_filename, last_created_at)

        if latest is None:
            return None
        filename, created_at = latest
        return SCREENSHOT_STORE[filename], filename, created_at, SCREENSHOT_METADATA.get(filename)


def list_agent_screenshots(agent_name: str, keep_minutes: int, limit: int, offset: int = 0) -> list[tuple[str, datetime]]:
    """List gallery screenshots that still have real image bytes in RAM."""
    cutoff = datetime.utcnow() - timedelta(minutes=keep_minutes)
    with _LOCK:
        rows = [
            (filename, created_at)
            for filename, created_at in SCREENSHOT_CREATED_AT.items()
            if SCREENSHOT_AGENT.get(filename) == agent_name
            and created_at >= cutoff
            and filename in SCREENSHOT_STORE
            and not _is_last_frame(filename)
        ]
    rows.sort(key=lambda item: item[1], reverse=True)
    return rows[offset:offset + limit]


def cleanup_ram_store(keep_minutes: int, max_per_agent: int | None = None) -> set[str]:
    """Remove old gallery frames while preserving each agent's *_last.jpg frame."""
    cutoff = datetime.utcnow() - timedelta(minutes=keep_minutes)
    with _LOCK:
        filenames_to_remove = {
            filename
            for filename, created_at in SCREENSHOT_CREATED_AT.items()
            if not _is_last_frame(filename)
            and (created_at < cutoff or filename not in SCREENSHOT_STORE)
        }

        if max_per_agent is not None and max_per_agent > 0:
            by_agent: dict[str, list[tuple[str, datetime]]] = {}
            for filename, created_at in SCREENSHOT_CREATED_AT.items():
                if (
                    filename in filenames_to_remove
                    or filename not in SCREENSHOT_STORE
                    or _is_last_frame(filename)
                ):
                    continue
                agent_name = SCREENSHOT_AGENT.get(filename)
                if agent_name is None:
                    continue
                by_agent.setdefault(agent_name, []).append((filename, created_at))
            for rows in by_agent.values():
                rows.sort(key=lambda item: item[1], reverse=True)
                filenames_to_remove.update(filename for filename, _ in rows[max_per_agent:])

        for filename in filenames_to_remove:
            SCREENSHOT_STORE.pop(filename, None)
            SCREENSHOT_CREATED_AT.pop(filename, None)
            SCREENSHOT_AGENT.pop(filename, None)
            SCREENSHOT_METADATA.pop(filename, None)
    return filenames_to_remove
