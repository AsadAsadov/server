import logging
from datetime import datetime, timedelta
from pathlib import Path
from database import get_db

logger = logging.getLogger(__name__)


def cleanup_server_screens(upload_folder: str, keep_minutes: int) -> None:
    base = Path(upload_folder)
    if not base.exists():
        return
    limit = datetime.utcnow() - timedelta(minutes=keep_minutes)

    conn = get_db()
    try:
        rows = conn.execute('SELECT filename FROM screenshots WHERE created_at < ?', (limit.isoformat(),)).fetchall()
        for row in rows:
            file_path = base / row['filename']
            try:
                if file_path.is_file() and file_path.parent.resolve() == base.resolve():
                    file_path.unlink()
                    logger.info('Old screenshot deleted: %s', file_path)
            except OSError:
                logger.exception('Could not delete screenshot file: %s', file_path)
        conn.execute('DELETE FROM screenshots WHERE created_at < ?', (limit.isoformat(),))
        conn.commit()
    finally:
        conn.close()

    # Safety net for orphan archive files; keep *_last.jpg live images.
    for file_path in base.iterdir():
        if not file_path.is_file() or file_path.name.endswith('_last.jpg'):
            continue
        try:
            file_time = datetime.utcfromtimestamp(min(file_path.stat().st_ctime, file_path.stat().st_mtime))
            if file_time < limit:
                file_path.unlink()
                logger.info('Old orphan screenshot deleted: %s', file_path)
        except OSError:
            logger.exception('Cleanup error for %s', file_path)
