import logging
from datetime import datetime, timedelta
from database import get_db

logger = logging.getLogger(__name__)


def cleanup_server_screens(keep_minutes: int, screenshot_store: dict[str, bytes] | None = None) -> None:
    """Remove old screenshot metadata and matching RAM-only image bytes."""
    limit = datetime.utcnow() - timedelta(minutes=keep_minutes)
    conn = get_db()
    try:
        rows = conn.execute('SELECT filename FROM screenshots WHERE created_at < ?', (limit.isoformat(),)).fetchall()
        if screenshot_store is not None:
            for row in rows:
                removed = screenshot_store.pop(row['filename'], None)
                if removed is not None:
                    logger.info('Old RAM screenshot deleted: %s', row['filename'])
        conn.execute('DELETE FROM screenshots WHERE created_at < ?', (limit.isoformat(),))
        conn.commit()
    finally:
        conn.close()
