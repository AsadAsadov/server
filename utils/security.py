import re
import secrets
from functools import wraps
from pathlib import Path
from flask import abort, redirect, request, session, url_for
from werkzeug.utils import secure_filename

_SAFE_NAME = re.compile(r'[^A-Za-z0-9_.-]+')


def safe_pc_name(value: str) -> str:
    value = (value or 'UNKNOWN').strip().replace(' ', '_')
    value = _SAFE_NAME.sub('_', value)
    value = secure_filename(value) or 'UNKNOWN'
    return value[:80]


def safe_screen_filename(filename: str) -> str:
    name = secure_filename(Path(filename).name)
    if not name or name in {'.', '..'}:
        abort(404)
    return name


def generate_csrf_token() -> str:
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


def validate_csrf() -> None:
    sent = request.form.get('_csrf_token', '')
    expected = session.get('_csrf_token', '')
    if not expected or not secrets.compare_digest(sent, expected):
        abort(400, description='Invalid CSRF token')


def csrf_protect(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            validate_csrf()
        return f(*args, **kwargs)
    return wrapper


def check_upload_token(expected: str) -> bool:
    if not expected:
        return False
    provided = request.headers.get('X-Upload-Token') or request.form.get('upload_token') or request.args.get('token')
    return bool(provided) and secrets.compare_digest(provided, expected)
