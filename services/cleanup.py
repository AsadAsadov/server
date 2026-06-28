import logging
from datetime import datetime, timedelta
from database import get_db
from services.ram_screens import SCREENSHOT_CREATED_AT

logger = logging.getLogger(__name__)


def cleanup_server_screens(
    keep_minutes: int,
    screenshot_store: dict[str, bytes] | None = None,
    max_per_agent: int | None = None,
) -> None:
    """Remove old screenshot metadata and matching RAM-only image bytes."""
    limit = datetime.utcnow() - timedelta(minutes=keep_minutes)
    filenames_to_remove: set[str] = set()
    conn = get_db()
    try:
        rows = conn.execute('SELECT filename FROM screenshots WHERE created_at < ?', (limit.isoformat(),)).fetchall()
        filenames_to_remove.update(row['filename'] for row in rows)
        conn.execute('DELETE FROM screenshots WHERE created_at < ?', (limit.isoformat(),))

        if max_per_agent is not None and max_per_agent > 0:
            agents = conn.execute('SELECT DISTINCT agent_name FROM screenshots').fetchall()
            for agent in agents:
                overflow = conn.execute('''
                    SELECT filename FROM screenshots
                    WHERE agent_name = ?
                    ORDER BY created_at DESC
                    LIMIT -1 OFFSET ?
                ''', (agent['agent_name'], max_per_agent)).fetchall()
                filenames_to_remove.update(row['filename'] for row in overflow)
                conn.execute('''
                    DELETE FROM screenshots
                    WHERE agent_name = ? AND filename IN (
                        SELECT filename FROM screenshots
                        WHERE agent_name = ?
                        ORDER BY created_at DESC
                        LIMIT -1 OFFSET ?
                    )
                ''', (agent['agent_name'], agent['agent_name'], max_per_agent))

        if screenshot_store is not None:
            for filename, created_at in list(SCREENSHOT_CREATED_AT.items()):
                if created_at < limit:
                    filenames_to_remove.add(filename)
            for filename in filenames_to_remove:
                removed = screenshot_store.pop(filename, None)
                SCREENSHOT_CREATED_AT.pop(filename, None)
                if removed is not None:
                    logger.info('Old RAM screenshot deleted: %s', filename)
        conn.commit()
    finally:
        conn.close()
