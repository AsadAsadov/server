import logging
import time
from datetime import datetime
from io import BytesIO
from flask import Blueprint, current_app, request, send_file
from auth import login_required
from database import get_db
from services.cleanup import cleanup_server_screens
from services.ram_screens import SCREENSHOT_STORE, get_screenshot, put_screenshot
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
    filename = safe_screen_filename(f'{pc_name}_{timestamp}.jpg')
    last_filename = safe_screen_filename(f'{pc_name}_last.jpg')

    data = file.read()
    put_screenshot(filename, data)
    put_screenshot(last_filename, data)

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
        cleanup_server_screens(current_app.config['KEEP_MINUTES'], SCREENSHOT_STORE)
        _LAST_CLEANUP = now_ts
    return 'OK', 200


@upload_bp.route('/screens/<path:filename>')
@login_required
def screens(filename):
    safe_name = safe_screen_filename(filename)
    data = get_screenshot(safe_name)
    if data is None:
        return 'Screenshot not found in RAM', 404
    return send_file(BytesIO(data), mimetype='image/jpeg', max_age=0)
