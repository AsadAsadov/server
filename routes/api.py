from datetime import datetime, timedelta
from flask import Blueprint, current_app, jsonify, request
from auth import login_required
from database import get_db
from services.cleanup import cleanup_server_screens
from services.ram_screens import SCREENSHOT_STORE, list_agent_screenshots
from utils.security import safe_pc_name
from utils.timezone import format_baku_time

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/agent/<agent_name>/last')
@login_required
def api_agent_last(agent_name):
    agent_name = safe_pc_name(agent_name)
    cleanup_server_screens(current_app.config['GALLERY_KEEP_MINUTES'], SCREENSHOT_STORE, current_app.config['MAX_RAM_SHOTS_PER_AGENT'])
    conn = get_db()
    row = conn.execute('''SELECT filename, created_at FROM screenshots WHERE agent_name = ? ORDER BY created_at DESC LIMIT 1''', (agent_name,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'ok': False}), 404
    return jsonify({'ok': True, 'filename': row['filename'], 'created_at': format_baku_time(row['created_at'])})


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
