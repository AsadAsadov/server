from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from auth import login_required
from services.ram_screens import ram_screens
from utils.security import safe_pc_name

api_bp = Blueprint('api', __name__)


def _fmt(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%d %H:%M:%S')


@api_bp.route('/api/agent/<agent_name>/last')
@login_required
def api_agent_last(agent_name):
    agent_name = safe_pc_name(agent_name)
    shot = ram_screens.get_last(agent_name)
    if not shot:
        return jsonify({'ok': False}), 404
    return jsonify({'ok': True, 'filename': shot.filename, 'created_at': _fmt(shot.created_at), 'metadata': shot.metadata})


@api_bp.route('/api/agent/<agent_name>/stats1h')
@login_required
def api_agent_stats1h(agent_name):
    agent_name = safe_pc_name(agent_name)
    since = datetime.utcnow() - timedelta(hours=1)
    buckets = ram_screens.count_by_minute(agent_name, since)
    labels = sorted(buckets.keys())
    return jsonify({'labels': labels, 'data': [buckets[k] for k in labels]})


@api_bp.route('/api/agent/<agent_name>/shots')
@login_required
def api_agent_shots(agent_name):
    agent_name = safe_pc_name(agent_name)
    offset = max(int(request.args.get('offset', 0)), 0)
    limit = min(max(int(request.args.get('limit', 60)), 1), 200)
    since = datetime.utcnow() - timedelta(hours=1)
    shots = ram_screens.list_recent(agent_name, since, offset, limit)
    return jsonify([{'filename': s.filename, 'created_at': _fmt(s.created_at)} for s in shots])
