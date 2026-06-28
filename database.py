import sqlite3
from config import Config


def get_db():
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


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
    cur.execute('CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_screenshots_agent_created ON screenshots(agent_name, created_at)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_employees_agent_name ON employees(agent_name)')
    conn.commit()
    conn.close()
