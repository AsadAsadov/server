from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request, session

from auth import login_required
from database import get_db
from services.remote_control import (
    RemoteControlError,
    RemoteSessionConflict,
    RemoteSessionInactive,
    RemoteSessionNotFound,
    remote_control_manager,
)
from utils.security import check_remote_agent_token, csrf_protect, safe_pc_name


remote_bp = Blueprint('remote', __name__)

_SPECIAL_KEYS = {
    'BACKSPACE', 'TAB', 'ENTER', 'SHIFT', 'CTRL', 'ALT', 'ESCAPE', 'SPACE',
    'PAGEUP', 'PAGEDOWN', 'END', 'HOME', 'ARROWLEFT', 'ARROWUP',
    'ARROWRIGHT', 'ARROWDOWN', 'INSERT', 'DELETE', 'CAPSLOCK', 'NUMLOCK',
    'SCROLLLOCK', 'PRINTSCREEN', 'PAUSE', 'CONTEXTMENU', 'META',
    'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
}


def _json_error(message, status_code):
    return jsonify({'ok': False, 'error': message}), status_code


def _agent_remote_status(agent_name):
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT last_seen, remote_capable FROM agents WHERE name = ?',
            (agent_name,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return {'exists': False, 'online': False, 'remote_capable': False}
    try:
        last_seen = datetime.fromisoformat(row['last_seen'])
    except (TypeError, ValueError):
        last_seen = datetime.min
    return {
        'exists': True,
        'online': last_seen >= datetime.utcnow() - timedelta(seconds=10),
        'remote_capable': bool(row['remote_capable']),
    }


def _normalize_key(value):
    key = str(value or '').strip().upper()
    aliases = {
        'CONTROL': 'CTRL',
        'ESC': 'ESCAPE',
        ' ': 'SPACE',
        'LEFT': 'ARROWLEFT',
        'RIGHT': 'ARROWRIGHT',
        'UP': 'ARROWUP',
        'DOWN': 'ARROWDOWN',
        'WIN': 'META',
        'OS': 'META',
    }
    key = aliases.get(key, key)
    if len(key) == 1 and (key.isalnum() or key in '+-*/.,;=[]\\\'`'):
        return key
    if key in _SPECIAL_KEYS:
        return key
    raise ValueError('Dəstəklənməyən klaviatura düyməsi')


def _normalize_command(command):
    if not isinstance(command, dict):
        raise ValueError('Komanda obyekt olmalıdır')
    command_type = str(command.get('type', '')).strip().lower()
    payload = command.get('payload') or {}
    if not isinstance(payload, dict):
        raise ValueError('Komanda payload-u obyekt olmalıdır')

    if command_type == 'move':
        x = float(payload.get('x'))
        y = float(payload.get('y'))
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            raise ValueError('Mouse koordinatları 0-1 aralığında olmalıdır')
        return {'type': 'move', 'payload': {'x': x, 'y': y}}

    if command_type == 'click':
        button = str(payload.get('button', 'left')).lower()
        if button not in {'left', 'right', 'middle'}:
            raise ValueError('Yanlış mouse düyməsi')
        count = int(payload.get('count', 1))
        if count not in {1, 2}:
            raise ValueError('Klik sayı 1 və ya 2 ola bilər')
        return {'type': 'click', 'payload': {'button': button, 'count': count}}

    if command_type == 'wheel':
        delta = int(payload.get('delta', 0))
        delta = max(-1200, min(1200, delta))
        if delta == 0:
            raise ValueError('Scroll dəyəri boşdur')
        return {'type': 'wheel', 'payload': {'delta': delta}}

    if command_type == 'text':
        text = str(payload.get('text', ''))
        if not text:
            raise ValueError('Mətn boşdur')
        if len(text) > 128:
            raise ValueError('Bir mətn komandası maksimum 128 simvol ola bilər')
        return {'type': 'text', 'payload': {'text': text}}

    if command_type == 'key':
        return {'type': 'key', 'payload': {'key': _normalize_key(payload.get('key'))}}

    if command_type == 'hotkey':
        keys = payload.get('keys')
        if not isinstance(keys, list) or not 2 <= len(keys) <= 4:
            raise ValueError('Hotkey 2-4 düymədən ibarət olmalıdır')
        normalized = [_normalize_key(key) for key in keys]
        return {'type': 'hotkey', 'payload': {'keys': normalized}}

    raise ValueError('Naməlum remote komanda')


@remote_bp.route('/api/remote/<agent_name>/start', methods=['POST'])
@login_required
@csrf_protect
def start_remote_session(agent_name):
    if not current_app.config['REMOTE_AGENT_TOKEN']:
        return _json_error('Serverdə REMOTE_AGENT_TOKEN qurulmayıb', 503)

    agent_name = safe_pc_name(agent_name)
    agent_status = _agent_remote_status(agent_name)
    if not agent_status['exists']:
        return _json_error('Agent tapılmadı', 404)
    if not agent_status['online']:
        return _json_error('Agent offline-dır və uzaqdan idarə edilə bilməz', 409)
    if not agent_status['remote_capable']:
        return _json_error('Bu kompüterdə remote dəstəkli yeni agent EXE quraşdırılmayıb', 409)

    try:
        remote_session = remote_control_manager.create_session(
            agent_name,
            session.get('email', 'admin'),
            current_app.config['REMOTE_SESSION_MINUTES'],
        )
    except RemoteSessionConflict as exc:
        return _json_error(str(exc), 409)
    except RemoteControlError as exc:
        return _json_error(str(exc), 400)

    return jsonify({'ok': True, 'session': remote_session}), 201


@remote_bp.route('/api/remote/<session_id>/status')
@login_required
def remote_session_status(session_id):
    try:
        remote_session = remote_control_manager.get_status(session_id, touch_admin=True)
    except RemoteSessionNotFound as exc:
        return _json_error(str(exc), 404)
    return jsonify({'ok': True, 'session': remote_session})


@remote_bp.route('/api/remote/<session_id>/commands', methods=['POST'])
@login_required
@csrf_protect
def enqueue_remote_commands(session_id):
    payload = request.get_json(silent=True) or {}
    commands = payload.get('commands')
    if not isinstance(commands, list) or not commands:
        return _json_error('Komanda siyahısı boşdur', 400)
    if len(commands) > 50:
        return _json_error('Bir sorğuda maksimum 50 komanda göndərilə bilər', 400)

    try:
        normalized = [_normalize_command(command) for command in commands]
        remote_session = remote_control_manager.enqueue_commands(session_id, normalized)
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except RemoteSessionNotFound as exc:
        return _json_error(str(exc), 404)
    except RemoteSessionInactive as exc:
        return _json_error(str(exc), 409)
    except RemoteControlError as exc:
        return _json_error(str(exc), 429)

    return jsonify({'ok': True, 'session': remote_session})


@remote_bp.route('/api/remote/<session_id>/stop', methods=['POST'])
@login_required
@csrf_protect
def stop_remote_session(session_id):
    try:
        remote_session = remote_control_manager.stop_session(session_id, 'admin_stopped')
    except RemoteSessionNotFound as exc:
        return _json_error(str(exc), 404)
    return jsonify({'ok': True, 'session': remote_session})


@remote_bp.route('/api/agent/remote/poll', methods=['POST'])
def agent_remote_poll():
    if not check_remote_agent_token(current_app.config['REMOTE_AGENT_TOKEN']):
        return _json_error('Unauthorized', 401)
    payload = request.get_json(silent=True) or request.form
    agent_name = safe_pc_name(payload.get('pc_name', 'UNKNOWN'))
    result = remote_control_manager.agent_poll(agent_name)
    return jsonify({'ok': True, **result})


@remote_bp.route('/api/agent/remote/state', methods=['POST'])
def agent_remote_state():
    if not check_remote_agent_token(current_app.config['REMOTE_AGENT_TOKEN']):
        return _json_error('Unauthorized', 401)
    payload = request.get_json(silent=True) or request.form
    agent_name = safe_pc_name(payload.get('pc_name', 'UNKNOWN'))
    session_id = str(payload.get('session_id', '')).strip()
    state = str(payload.get('state', '')).strip().lower()
    message = str(payload.get('message', '')).strip()
    if not session_id:
        return _json_error('session_id boşdur', 400)

    try:
        remote_session = remote_control_manager.agent_state(
            agent_name,
            session_id,
            state,
            message,
        )
    except RemoteSessionNotFound as exc:
        return _json_error(str(exc), 404)
    except RemoteControlError as exc:
        return _json_error(str(exc), 400)

    return jsonify({'ok': True, 'session': remote_session})
