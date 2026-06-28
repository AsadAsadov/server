from datetime import datetime, timedelta
from database import get_db
from services.ram_screens import ram_screens


def cleanup_server_screens(keep_minutes: int, max_per_agent: int) -> None:
    """Cleanup RAM screenshots and old metadata rows; never touch image files."""
    limit = datetime.utcnow() - timedelta(minutes=keep_minutes)
    ram_screens.cleanup(keep_minutes, max_per_agent)
    conn = get_db()
    try:
        conn.execute('DELETE FROM screenshots WHERE created_at < ?', (limit.isoformat(),))
        conn.commit()
    finally:
        conn.close()
