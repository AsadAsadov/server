import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from config import Config
from database import get_db


AGENT_NAME = 'TEST-REMOTE-AGENT'
CSRF_TOKEN = 'test-remote-csrf-token'


def prepare_agent():
    conn = get_db()
    try:
        conn.execute('''
            INSERT INTO agents (
                name, last_seen, active_window, active_process, process_list,
                agent_version, remote_capable
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                last_seen = excluded.last_seen,
                agent_version = excluded.agent_version,
                remote_capable = excluded.remote_capable
        ''', (
            AGENT_NAME,
            datetime.utcnow().isoformat(),
            'Remote test window',
            'test.exe',
            'test.exe',
            '2.1.0-remote-test',
            1,
        ))
        conn.commit()
    finally:
        conn.close()


def cleanup():
    conn = get_db()
    try:
        conn.execute('DELETE FROM agents WHERE name = ?', (AGENT_NAME,))
        conn.execute('DELETE FROM employees WHERE agent_name = ?', (AGENT_NAME,))
        conn.execute('DELETE FROM screenshots WHERE agent_name = ?', (AGENT_NAME,))
        conn.execute('DELETE FROM activity_events WHERE agent_name = ?', (AGENT_NAME,))
        conn.execute('DELETE FROM remote_session_audit WHERE agent_name = ?', (AGENT_NAME,))
        conn.commit()
    finally:
        conn.close()


def main():
    if not Config.REMOTE_AGENT_TOKEN:
        raise RuntimeError('REMOTE_AGENT_TOKEN test mühitində boşdur')

    prepare_agent()
    try:
        with app.test_client() as client:
            with client.session_transaction() as browser_session:
                browser_session['logged_in'] = True
                browser_session['email'] = 'remote-test@localhost'
                browser_session['_csrf_token'] = CSRF_TOKEN

            response = client.post(
                '/api/remote/{0}/start'.format(AGENT_NAME),
                json={},
                headers={'X-CSRF-Token': CSRF_TOKEN},
            )
            assert response.status_code == 201, response.get_data(as_text=True)
            remote_session = response.get_json()['session']
            session_id = remote_session['id']
            print('START:', response.status_code, remote_session['status'])

            response = client.post(
                '/api/agent/remote/poll',
                json={'pc_name': AGENT_NAME},
                headers={'X-Remote-Token': Config.REMOTE_AGENT_TOKEN},
            )
            assert response.status_code == 200
            assert response.get_json()['session']['status'] == 'pending'
            print('AGENT POLL: pending')

            response = client.post(
                '/api/agent/remote/state',
                json={
                    'pc_name': AGENT_NAME,
                    'session_id': session_id,
                    'state': 'accepted',
                    'message': 'test accepted',
                },
                headers={'X-Remote-Token': Config.REMOTE_AGENT_TOKEN},
            )
            assert response.status_code == 200
            assert response.get_json()['session']['status'] == 'active'
            print('AGENT STATE: active')

            commands = [
                {'type': 'move', 'payload': {'x': 0.25, 'y': 0.75}},
                {'type': 'click', 'payload': {'button': 'left', 'count': 1}},
                {'type': 'text', 'payload': {'text': 'Salam'}},
                {'type': 'hotkey', 'payload': {'keys': ['CTRL', 'A']}},
            ]
            response = client.post(
                '/api/remote/{0}/commands'.format(session_id),
                json={'commands': commands},
                headers={'X-CSRF-Token': CSRF_TOKEN},
            )
            assert response.status_code == 200, response.get_data(as_text=True)
            print('COMMAND QUEUE:', response.get_json()['session']['queue_size'])

            response = client.post(
                '/api/agent/remote/poll',
                json={'pc_name': AGENT_NAME},
                headers={'X-Remote-Token': Config.REMOTE_AGENT_TOKEN},
            )
            payload = response.get_json()
            assert response.status_code == 200
            assert payload['session']['status'] == 'active'
            assert len(payload['commands']) == 4, payload
            print('AGENT RECEIVED:', len(payload['commands']))

            response = client.post(
                '/api/remote/{0}/stop'.format(session_id),
                json={},
                headers={'X-CSRF-Token': CSRF_TOKEN},
            )
            assert response.status_code == 200
            assert response.get_json()['session']['status'] == 'ended'
            print('STOP:', response.get_json()['session']['ended_reason'])

        print('REMOTE MVP SERVER TEST: OK')
    finally:
        cleanup()


if __name__ == '__main__':
    main()
