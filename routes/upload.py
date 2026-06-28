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

ACTIVITY_CHANGE_THRESHOLD_SECONDS = 5


def _optional_float(value):
    try:
        return float(value) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


def _same_activity(row, active_process, active_window, active_url):
    return (
        (row['active_process'] or '') == (active_process or '')
        and (row['active_window'] or '') == (active_window or '')
        and (row['active_url'] or '') == (active_url or '')
    )


def _track_activity(cur, agent_name, active_process, active_window, active_url, now):
    open_event = cur.execute('''
        SELECT * FROM activity_events
        WHERE agent_name = ? AND ended_at IS NULL
        ORDER BY started_at DESC LIMIT 1
    ''', (agent_name,)).fetchone()
    if open_event and _same_activity(open_event, active_process, active_window, active_url):
        return

    if open_event:
        try:
            started_at = datetime.fromisoformat(open_event['started_at'])
        except (TypeError, ValueError):
            started_at = now
        duration = max(int((now - started_at).total_seconds()), 0)
        if duration < ACTIVITY_CHANGE_THRESHOLD_SECONDS:
            cur.execute('''
                UPDATE activity_events
                SET active_process = ?, active_window = ?, active_url = ?, started_at = ?
                WHERE id = ?
            ''', (active_process, active_window, active_url, now.isoformat(), open_event['id']))
            return
        cur.execute('''
            UPDATE activity_events
            SET ended_at = ?, duration_seconds = ?
            WHERE id = ?
        ''', (now.isoformat(), duration, open_event['id']))

    cur.execute('''
        INSERT INTO activity_events (agent_name, active_process, active_window, active_url, started_at, ended_at, duration_seconds)
        VALUES (?, ?, ?, ?, ?, NULL, NULL)
    ''', (agent_name, active_process, active_window, active_url, now.isoformat()))

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
    active_url = request.form.get('active_url', '')
    mouse_x = _optional_float(request.form.get('mouse_x'))
    mouse_y = _optional_float(request.form.get('mouse_y'))
    screen_width = _optional_float(request.form.get('screen_width'))
    screen_height = _optional_float(request.form.get('screen_height'))
    file = request.files.get('screenshot')
    if not file:
        return 'No file', 400

    now = datetime.utcnow()
    timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')
    filename = safe_screen_filename(f'{pc_name}_{timestamp}.jpg')
    last_filename = safe_screen_filename(f'{pc_name}_last.jpg')

    data = file.read()
    put_screenshot(filename, data, now, pc_name)
    put_screenshot(last_filename, data, now)

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO agents (name, last_seen, active_window, active_process, process_list, mouse_x, mouse_y, screen_width, screen_height, active_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                last_seen=excluded.last_seen,
                active_window=excluded.active_window,
                active_process=excluded.active_process,
                process_list=excluded.process_list,
                mouse_x=excluded.mouse_x,
                mouse_y=excluded.mouse_y,
                screen_width=excluded.screen_width,
                screen_height=excluded.screen_height,
                active_url=excluded.active_url
        ''', (pc_name, now.isoformat(), active_window, active_process, process_list, mouse_x, mouse_y, screen_width, screen_height, active_url))
        cur.execute('INSERT INTO screenshots (agent_name, filename, created_at) VALUES (?, ?, ?)', (pc_name, filename, now.isoformat()))
        _track_activity(cur, pc_name, active_process, active_window, active_url, now)
        conn.commit()
    finally:
        conn.close()

    now_ts = time.time()
    if now_ts - _LAST_CLEANUP >= 60:
        cleanup_server_screens(
            current_app.config['GALLERY_KEEP_MINUTES'],
            SCREENSHOT_STORE,
            current_app.config['MAX_RAM_SHOTS_PER_AGENT'],
        )
        _LAST_CLEANUP = now_ts
    return 'OK', 200


@upload_bp.route('/screens/<path:filename>')
@login_required
def screens(filename):
    cleanup_server_screens(
        current_app.config['GALLERY_KEEP_MINUTES'],
        SCREENSHOT_STORE,
        current_app.config['MAX_RAM_SHOTS_PER_AGENT'],
    )
    safe_name = safe_screen_filename(filename)
    data = get_screenshot(safe_name)
    if data is None:
        return 'Screenshot not found in RAM', 404
    return send_file(BytesIO(data), mimetype='image/jpeg', max_age=0)
