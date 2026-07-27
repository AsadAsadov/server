import secrets
from collections import deque
from datetime import datetime, timedelta
from threading import RLock

from database import get_db


class RemoteControlError(Exception):
    pass


class RemoteSessionNotFound(RemoteControlError):
    pass


class RemoteSessionConflict(RemoteControlError):
    pass


class RemoteSessionInactive(RemoteControlError):
    pass


class RemoteControlManager:
    def __init__(self):
        self._lock = RLock()
        self._sessions = {}
        self._agent_sessions = {}

    @staticmethod
    def _utcnow():
        return datetime.utcnow()

    @staticmethod
    def _iso(value):
        return value.isoformat() if value else None

    def _audit_start(self, session):
        conn = get_db()
        try:
            conn.execute('''
                INSERT INTO remote_session_audit (
                    session_id, agent_name, admin_email, status,
                    started_at, accepted_at, ended_at, ended_reason,
                    command_count, agent_last_poll
                ) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, 0, NULL)
            ''', (
                session['id'],
                session['agent_name'],
                session['admin_email'],
                session['status'],
                self._iso(session['created_at']),
            ))
            conn.commit()
        finally:
            conn.close()

    def _audit_update(self, session):
        conn = get_db()
        try:
            conn.execute('''
                UPDATE remote_session_audit
                SET status = ?, accepted_at = ?, ended_at = ?,
                    ended_reason = ?, command_count = ?, agent_last_poll = ?
                WHERE session_id = ?
            ''', (
                session['status'],
                self._iso(session.get('accepted_at')),
                self._iso(session.get('ended_at')),
                session.get('ended_reason'),
                session.get('command_count', 0),
                self._iso(session.get('last_agent_poll')),
                session['id'],
            ))
            conn.commit()
        finally:
            conn.close()

    def _end_locked(self, session, reason):
        if session.get('ended_at'):
            return
        session['status'] = 'ended'
        session['ended_at'] = self._utcnow()
        session['ended_reason'] = reason
        session['commands'].clear()
        if self._agent_sessions.get(session['agent_name']) == session['id']:
            self._agent_sessions.pop(session['agent_name'], None)
        self._audit_update(session)

    def _cleanup_locked(self):
        now = self._utcnow()
        for session in list(self._sessions.values()):
            if session.get('ended_at'):
                continue
            if now >= session['expires_at']:
                self._end_locked(session, 'expired')
                continue
            if session['status'] == 'pending' and now - session['created_at'] > timedelta(seconds=90):
                self._end_locked(session, 'consent_timeout')
                continue
            if session['status'] == 'active':
                if now - session['last_admin_seen'] > timedelta(seconds=20):
                    self._end_locked(session, 'admin_disconnected')
                    continue
                last_poll = session.get('last_agent_poll')
                if last_poll and now - last_poll > timedelta(seconds=20):
                    self._end_locked(session, 'agent_disconnected')

    def create_session(self, agent_name, admin_email, duration_minutes=30):
        with self._lock:
            self._cleanup_locked()
            existing_id = self._agent_sessions.get(agent_name)
            if existing_id:
                existing = self._sessions.get(existing_id)
                if existing and not existing.get('ended_at'):
                    raise RemoteSessionConflict('Bu agent üçün artıq aktiv sessiya var')

            now = self._utcnow()
            session_id = secrets.token_urlsafe(32)
            session = {
                'id': session_id,
                'agent_name': agent_name,
                'admin_email': admin_email,
                'status': 'pending',
                'created_at': now,
                'accepted_at': None,
                'expires_at': now + timedelta(minutes=max(1, min(int(duration_minutes), 120))),
                'ended_at': None,
                'ended_reason': None,
                'last_admin_seen': now,
                'last_agent_poll': None,
                'commands': deque(),
                'command_count': 0,
                'sequence': 0,
                'agent_message': '',
            }
            self._sessions[session_id] = session
            self._agent_sessions[agent_name] = session_id
            self._audit_start(session)
            return self._public_session(session)

    def _get_locked(self, session_id):
        self._cleanup_locked()
        session = self._sessions.get(session_id)
        if not session:
            raise RemoteSessionNotFound('Sessiya tapılmadı')
        return session

    def _public_session(self, session):
        now = self._utcnow()
        last_agent_poll = session.get('last_agent_poll')
        return {
            'id': session['id'],
            'agent_name': session['agent_name'],
            'status': session['status'],
            'created_at': self._iso(session['created_at']),
            'accepted_at': self._iso(session.get('accepted_at')),
            'expires_at': self._iso(session['expires_at']),
            'ended_at': self._iso(session.get('ended_at')),
            'ended_reason': session.get('ended_reason'),
            'agent_connected': bool(last_agent_poll and now - last_agent_poll <= timedelta(seconds=5)),
            'agent_message': session.get('agent_message', ''),
            'command_count': session.get('command_count', 0),
            'queue_size': len(session['commands']),
        }

    def get_status(self, session_id, touch_admin=True):
        with self._lock:
            session = self._get_locked(session_id)
            if touch_admin and not session.get('ended_at'):
                session['last_admin_seen'] = self._utcnow()
            return self._public_session(session)

    def enqueue_commands(self, session_id, commands):
        with self._lock:
            session = self._get_locked(session_id)
            if session['status'] != 'active' or session.get('ended_at'):
                raise RemoteSessionInactive('Sessiya idarəetmə üçün aktiv deyil')

            for command in commands:
                command_type = command['type']
                session['sequence'] += 1
                queued = {
                    'id': session['sequence'],
                    'type': command_type,
                    'payload': command.get('payload', {}),
                    'created_at': self._iso(self._utcnow()),
                }

                if command_type == 'move' and session['commands'] and session['commands'][-1]['type'] == 'move':
                    session['commands'][-1] = queued
                    continue

                if len(session['commands']) >= 500:
                    removed = False
                    for index, pending in enumerate(session['commands']):
                        if pending['type'] == 'move':
                            del session['commands'][index]
                            removed = True
                            break
                    if not removed:
                        raise RemoteControlError('Komanda növbəsi doludur')

                session['commands'].append(queued)
                session['command_count'] += 1

            return self._public_session(session)

    def stop_session(self, session_id, reason='admin_stopped'):
        with self._lock:
            session = self._get_locked(session_id)
            self._end_locked(session, reason)
            return self._public_session(session)

    def agent_poll(self, agent_name, limit=100):
        with self._lock:
            self._cleanup_locked()
            session_id = self._agent_sessions.get(agent_name)
            if not session_id:
                return {'session': None, 'commands': []}
            session = self._sessions.get(session_id)
            if not session or session.get('ended_at'):
                return {'session': None, 'commands': []}

            session['last_agent_poll'] = self._utcnow()
            commands = []
            if session['status'] == 'active':
                for _ in range(min(max(int(limit), 1), 100)):
                    if not session['commands']:
                        break
                    commands.append(session['commands'].popleft())

            return {
                'session': self._public_session(session),
                'commands': commands,
            }

    def agent_state(self, agent_name, session_id, state, message=''):
        with self._lock:
            session = self._get_locked(session_id)
            if session['agent_name'] != agent_name:
                raise RemoteSessionNotFound('Sessiya bu agentə aid deyil')
            if session.get('ended_at'):
                return self._public_session(session)

            session['last_agent_poll'] = self._utcnow()
            session['agent_message'] = str(message or '')[:300]

            if state == 'accepted':
                session['status'] = 'active'
                session['accepted_at'] = self._utcnow()
                session['last_admin_seen'] = self._utcnow()
                self._audit_update(session)
            elif state in {'denied', 'stopped', 'error'}:
                self._end_locked(session, 'agent_' + state)
            else:
                raise RemoteControlError('Naməlum agent statusu')

            return self._public_session(session)


remote_control_manager = RemoteControlManager()
