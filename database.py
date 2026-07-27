import sqlite3
from config import Config


def get_db():
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def _ensure_column(cur, table, column, definition):
    columns = [row['name'] for row in cur.execute(f'PRAGMA table_info({table})').fetchall()]
    if column not in columns:
        cur.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            last_seen TEXT,
            active_window TEXT,
            active_process TEXT,
            process_list TEXT
        )
    ''')
    _ensure_column(cur, 'agents', 'mouse_x', 'REAL')
    _ensure_column(cur, 'agents', 'mouse_y', 'REAL')
    _ensure_column(cur, 'agents', 'screen_width', 'REAL')
    _ensure_column(cur, 'agents', 'screen_height', 'REAL')
    _ensure_column(cur, 'agents', 'active_url', 'TEXT')
    _ensure_column(cur, 'agents', 'agent_version', 'TEXT')
    _ensure_column(cur, 'agents', 'remote_capable', 'INTEGER NOT NULL DEFAULT 0')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            filename TEXT,
            created_at TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT UNIQUE,
            full_name TEXT,
            department TEXT,
            role TEXT,
            note TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS activity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            active_process TEXT,
            active_window TEXT,
            active_url TEXT,
            started_at TEXT,
            ended_at TEXT,
            duration_seconds INTEGER
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS remote_session_audit (
            session_id TEXT PRIMARY KEY,
            agent_name TEXT NOT NULL,
            admin_email TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            accepted_at TEXT,
            ended_at TEXT,
            ended_reason TEXT,
            command_count INTEGER NOT NULL DEFAULT 0,
            agent_last_poll TEXT
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_screenshots_agent_created ON screenshots(agent_name, created_at)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_employees_agent_name ON employees(agent_name)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_activity_agent_started ON activity_events(agent_name, started_at)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_activity_agent_open ON activity_events(agent_name, ended_at)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_remote_audit_agent_started ON remote_session_audit(agent_name, started_at)')
    conn.commit()
    conn.close()
