import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(BASE_DIR / '.env')


class Config:
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', '')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-this-secret-key')
    # Kept only for backward-compatible environment files; screenshots are RAM-only.
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'screens'))
    DB_PATH = os.getenv('DB_PATH', str(BASE_DIR / 'monitor.db'))
    KEEP_MINUTES = int(os.getenv('KEEP_MINUTES', '60'))
    MAX_RAM_SHOTS_PER_AGENT = int(os.getenv('MAX_RAM_SHOTS_PER_AGENT', '300'))
    UPLOAD_TOKEN = os.getenv('UPLOAD_TOKEN', '')

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', '0') == '1'
    PERMANENT_SESSION_LIFETIME_MINUTES = int(os.getenv('SESSION_LIFETIME_MINUTES', '480'))
