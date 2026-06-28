import secrets
from functools import wraps
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from utils.security import csrf_protect

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapper


@auth_bp.route('/login', methods=['GET', 'POST'])
@csrf_protect
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        admin_email = current_app.config['ADMIN_EMAIL']
        admin_password = current_app.config['ADMIN_PASSWORD']
        if admin_email and admin_password and secrets.compare_digest(email, admin_email) and secrets.compare_digest(password, admin_password):
            session.clear()
            session.permanent = True
            session['logged_in'] = True
            session['email'] = email
            return redirect(url_for('main.dashboard'))
        error = 'Email və ya şifrə yanlışdır.'
    return render_template('login.html', error=error)


@auth_bp.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
