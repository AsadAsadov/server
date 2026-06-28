import logging
from datetime import datetime, timedelta
from database import get_db
from services.ram_screens import cleanup_ram_store

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
            filenames_to_remove.update(cleanup_ram_store(keep_minutes, max_per_agent))
            stale_rows = conn.execute('SELECT filename FROM screenshots').fetchall()
            for row in stale_rows:
                if row['filename'] not in screenshot_store:
                    filenames_to_remove.add(row['filename'])
            if filenames_to_remove:
                conn.executemany(
                    'DELETE FROM screenshots WHERE filename = ?',
                    [(filename,) for filename in filenames_to_remove],
                )
            for filename in filenames_to_remove:
                logger.info('Old screenshot metadata cleaned: %s', filename)
        conn.commit()
    finally:
        conn.close()
