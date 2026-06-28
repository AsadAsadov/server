from datetime import datetime, timedelta
from flask import Blueprint, current_app, jsonify, request
from auth import login_required
from database import get_db
from services.cleanup import cleanup_server_screens
from services.ram_screens import SCREENSHOT_STORE, list_agent_screenshots
from utils.security import safe_pc_name
from utils.timezone import format_baku_time


def _format_duration(seconds):
    seconds = max(int(seconds or 0), 0)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f'{hours}s {minutes}d'
    if minutes:
        return f'{minutes}d {secs}san'
    return f'{secs}san'

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/agent/<agent_name>/last')
@login_required
def api_agent_last(agent_name):
    agent_name = safe_pc_name(agent_name)
    cleanup_server_screens(current_app.config['GALLERY_KEEP_MINUTES'], SCREENSHOT_STORE, current_app.config['MAX_RAM_SHOTS_PER_AGENT'])
    conn = get_db()
    row = conn.execute('''SELECT filename, created_at FROM screenshots WHERE agent_name = ? ORDER BY created_at DESC LIMIT 1''', (agent_name,)).fetchone()
    agent = conn.execute('''SELECT mouse_x, mouse_y, screen_width, screen_height, active_url FROM agents WHERE name = ?''', (agent_name,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'ok': False}), 404
    payload = {'ok': True, 'filename': row['filename'], 'created_at': format_baku_time(row['created_at'])}
    if agent:
        payload.update({
            'mouse_x': agent['mouse_x'],
            'mouse_y': agent['mouse_y'],
            'screen_width': agent['screen_width'],
            'screen_height': agent['screen_height'],
            'active_url': agent['active_url'],
        })
    return jsonify(payload)


@api_bp.route('/api/agent/<agent_name>/stats1h')
@login_required
def api_agent_stats1h(agent_name):
    agent_name = safe_pc_name(agent_name)
    since = datetime.utcnow() - timedelta(hours=1)
    conn = get_db()
    rows = conn.execute('SELECT created_at FROM screenshots WHERE agent_name = ? AND created_at >= ?', (agent_name, since.isoformat())).fetchall()
    conn.close()
    buckets = {}
    for r in rows:
        dt = datetime.fromisoformat(r['created_at'])
        key = dt.strftime('%H:%M')
        buckets[key] = buckets.get(key, 0) + 1
    labels = sorted(buckets.keys())
    return jsonify({'labels': labels, 'data': [buckets[k] for k in labels]})


@api_bp.route('/api/agent/<agent_name>/shots')
@login_required
def api_agent_shots(agent_name):
    agent_name = safe_pc_name(agent_name)
    offset = max(int(request.args.get('offset', 0)), 0)
    limit = min(max(int(request.args.get('limit', 60)), 1), 200)
    cleanup_server_screens(current_app.config['GALLERY_KEEP_MINUTES'], SCREENSHOT_STORE, current_app.config['MAX_RAM_SHOTS_PER_AGENT'])
    rows = list_agent_screenshots(
        agent_name,
        current_app.config['GALLERY_KEEP_MINUTES'],
        limit,
        offset,
    )
    return jsonify([{'filename': filename, 'created_at': format_baku_time(created_at)} for filename, created_at in rows])


@api_bp.route('/api/agent/<agent_name>/activity/today')
@login_required
def api_agent_activity_today(agent_name):
    agent_name = safe_pc_name(agent_name)
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    conn = get_db()
    rows = conn.execute('''
        SELECT active_process, active_window, active_url, started_at, ended_at, duration_seconds
        FROM activity_events
        WHERE agent_name = ? AND started_at >= ?
        ORDER BY started_at ASC
    ''', (agent_name, today_start.isoformat())).fetchall()
    conn.close()

    grouped = {}
    for row in rows:
        try:
            started_at = datetime.fromisoformat(row['started_at'])
        except (TypeError, ValueError):
            started_at = now
        if row['ended_at']:
            try:
                ended_at = datetime.fromisoformat(row['ended_at'])
            except (TypeError, ValueError):
                ended_at = now
        else:
            ended_at = now
        duration = row['duration_seconds'] if row['duration_seconds'] is not None else int((ended_at - started_at).total_seconds())
        key = (row['active_process'] or '—', row['active_window'] or '', row['active_url'] or '')
        item = grouped.setdefault(key, {
            'process': key[0],
            'window': key[1],
            'url': key[2],
            'total_seconds': 0,
            'first_seen_raw': started_at,
            'last_seen_raw': ended_at,
        })
        item['total_seconds'] += max(int(duration or 0), 0)
        item['first_seen_raw'] = min(item['first_seen_raw'], started_at)
        item['last_seen_raw'] = max(item['last_seen_raw'], ended_at)

    activities = sorted(grouped.values(), key=lambda item: item['total_seconds'], reverse=True)
    for item in activities:
        item['formatted_duration'] = _format_duration(item['total_seconds'])
        item['first_seen'] = format_baku_time(item.pop('first_seen_raw'))
        item['last_seen'] = format_baku_time(item.pop('last_seen_raw'))
    return jsonify({'ok': True, 'activities': activities})
