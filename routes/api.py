from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from auth import login_required
from database import get_db
from utils.security import safe_pc_name

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/agent/<agent_name>/last')
@login_required
def api_agent_last(agent_name):
    agent_name = safe_pc_name(agent_name)
    conn = get_db()
    row = conn.execute('''SELECT filename, created_at FROM screenshots WHERE agent_name = ? ORDER BY created_at DESC LIMIT 1''', (agent_name,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'ok': False}), 404
    return jsonify({'ok': True, 'filename': row['filename'], 'created_at': row['created_at']})


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
    since = datetime.utcnow() - timedelta(hours=1)
    conn = get_db()
    rows = conn.execute('''
        SELECT filename, created_at FROM screenshots
        WHERE agent_name = ? AND created_at >= ?
        ORDER BY created_at DESC LIMIT ? OFFSET ?
    ''', (agent_name, since.isoformat(), limit, offset)).fetchall()
    conn.close()
    return jsonify([{'filename': r['filename'], 'created_at': datetime.fromisoformat(r['created_at']).strftime('%Y-%m-%d %H:%M:%S')} for r in rows])
