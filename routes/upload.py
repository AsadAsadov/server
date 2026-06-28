import io
import logging
import time
from datetime import datetime
from flask import Blueprint, current_app, request, send_file
from auth import login_required
from database import get_db
from services.cleanup import cleanup_server_screens
from services.ram_screens import ram_screens
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

    data = file.read()
    if not data:
        return 'Empty file', 400

    now = datetime.utcnow()
    timestamp = now.strftime('%Y-%m-%d_%H-%M-%S_%f')
    filename = safe_screen_filename(f'{pc_name}_{timestamp}.jpg')
    metadata = {
        'active_window': active_window,
        'active_process': active_process,
        'process_list': process_list,
    }
    ram_screens.put(
        pc_name,
        filename,
        data,
        now,
        metadata,
        current_app.config['KEEP_MINUTES'],
        current_app.config['MAX_RAM_SHOTS_PER_AGENT'],
    )

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
    except Exception:
        logger.exception('Failed saving upload metadata for pc=%s', pc_name)
        return 'Metadata write error', 500
    finally:
        conn.close()

    now_ts = time.time()
    if now_ts - _LAST_CLEANUP >= 600:
        cleanup_server_screens(current_app.config['KEEP_MINUTES'], current_app.config['MAX_RAM_SHOTS_PER_AGENT'])
        _LAST_CLEANUP = now_ts
    return 'OK', 200


@upload_bp.route('/screens/<path:filename>')
@login_required
def screens(filename):
    shot = ram_screens.get_by_filename(safe_screen_filename(filename))
    if not shot:
        return 'Screenshot not found in RAM', 404
    return send_file(io.BytesIO(shot.data), mimetype='image/jpeg', download_name=shot.filename, max_age=0)
