import logging
import time
from datetime import datetime
from pathlib import Path
from flask import Blueprint, current_app, request, send_from_directory
from auth import login_required
from database import get_db
from services.cleanup import cleanup_server_screens
from utils.security import check_upload_token, safe_pc_name, safe_screen_filename

upload_bp = Blueprint('upload', __name__)
logger = logging.getLogger(__name__)
_LAST_CLEANUP = 0


@upload_bp.route('/upload', methods=['POST'])
def upload():
    global _LAST_CLEANUP
    if not check_upload_token(current_app.config['UPLOAD_TOKEN']):
        return 'Unauthorized', 401

    pc_name = safe_pc_name(request.form.get('pc_name', 'UNKNOWN'))
    active_window = request.form.get('active_window', '')
    active_process = request.form.get('active_process', '')
    process_list = request.form.get('process_list', '')
    file = request.files.get('screenshot')
    if not file:
        return 'No file', 400

    now = datetime.utcnow()
    timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')
    upload_dir = Path(current_app.config['UPLOAD_FOLDER'])
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_screen_filename(f'{pc_name}_{timestamp}.jpg')
    full_path = upload_dir / filename
    last_image = upload_dir / safe_screen_filename(f'{pc_name}_last.jpg')

    try:
        data = file.read()
        full_path.write_bytes(data)
        last_image.write_bytes(data)
    except OSError:
        logger.exception('Failed writing upload for pc=%s', pc_name)
        return 'File write error', 500

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO agents (name, last_seen, active_window, active_process, process_list)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                last_seen=excluded.last_seen,
                active_window=excluded.active_window,
                active_process=excluded.active_process,
                process_list=excluded.process_list
        ''', (pc_name, now.isoformat(), active_window, active_process, process_list))
        cur.execute('INSERT INTO screenshots (agent_name, filename, created_at) VALUES (?, ?, ?)', (pc_name, filename, now.isoformat()))
        conn.commit()
    finally:
        conn.close()

    now_ts = time.time()
    if now_ts - _LAST_CLEANUP >= 600:
        cleanup_server_screens(current_app.config['UPLOAD_FOLDER'], current_app.config['KEEP_MINUTES'])
        _LAST_CLEANUP = now_ts
    return 'OK', 200


@upload_bp.route('/screens/<path:filename>')
@login_required
def screens(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], safe_screen_filename(filename))
