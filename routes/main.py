from datetime import datetime, timedelta
from flask import Blueprint, redirect, render_template, request, url_for
from auth import login_required
from database import get_db
from utils.security import csrf_protect, safe_pc_name
from utils.timezone import format_baku

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def dashboard():
    now = datetime.utcnow()
    online_threshold = now - timedelta(seconds=10)
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM agents ORDER BY name ASC')
    agents_rows = cur.fetchall()
    cur.execute('SELECT * FROM employees')
    emps_rows = cur.fetchall()

    emp_by_agent = {e['agent_name']: e for e in emps_rows}
    agents = []
    for a in agents_rows:
        name = a['name']
        try:
            last_seen = datetime.fromisoformat(a['last_seen'])
        except (TypeError, ValueError):
            last_seen = datetime.min
        emp = emp_by_agent.get(name)
        last_shot = conn.execute(
            'SELECT filename FROM screenshots WHERE agent_name = ? ORDER BY created_at DESC LIMIT 1',
            (name,),
        ).fetchone()
        agents.append({
            'name': name,
            'last_seen': last_seen,
            'last_seen_display': format_baku(last_seen),
            'online': last_seen >= online_threshold,
            'full_name': emp['full_name'] if emp and emp['full_name'] else None,
            'department': emp['department'] if emp else None,
            'role': emp['role'] if emp else None,
            'active_window': a['active_window'],
            'active_process': a['active_process'],
            'last_filename': last_shot['filename'] if last_shot else None,
        })
    conn.close()
    return render_template('dashboard.html', agents=agents)


@main_bp.route('/employees', methods=['GET', 'POST'])
@login_required
@csrf_protect
def employees():
    conn = get_db()
    cur = conn.cursor()
    if request.method == 'POST':
        agent_name = safe_pc_name(request.form.get('agent_name'))
        cur.execute('''
            INSERT INTO employees (agent_name, full_name, department, role, note)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(agent_name) DO UPDATE SET
                full_name=excluded.full_name,
                department=excluded.department,
                role=excluded.role,
                note=excluded.note
        ''', (
            agent_name,
            request.form.get('full_name', ''),
            request.form.get('department', ''),
            request.form.get('role', ''),
            request.form.get('note', ''),
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('main.employees'))

    cur.execute('SELECT * FROM agents ORDER BY name ASC')
    agents_rows = cur.fetchall()
    cur.execute('SELECT * FROM employees')
    emps_rows = cur.fetchall()
    conn.close()
    emp_map = {e['agent_name']: e for e in emps_rows}
    rows = []
    for a in agents_rows:
        e = emp_map.get(a['name'])
        rows.append({
            'agent_name': a['name'],
            'full_name': e['full_name'] if e else '',
            'department': e['department'] if e else '',
            'role': e['role'] if e else '',
            'note': e['note'] if e else '',
        })
    return render_template('employees.html', rows=rows)


@main_bp.route('/agent/<agent_name>')
@login_required
def agent_detail(agent_name):
    agent_name = safe_pc_name(agent_name)
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM agents WHERE name = ?', (agent_name,))
    a = cur.fetchone()
    if not a:
        conn.close()
        return f'Agent tapılmadı: {agent_name}', 404
    cur.execute('SELECT * FROM employees WHERE agent_name = ?', (agent_name,))
    emp = cur.fetchone()
    conn.close()
    last_seen = datetime.fromisoformat(a['last_seen'])
    is_online = last_seen >= datetime.utcnow() - timedelta(seconds=10)
    return render_template(
        'agent_detail.html',
        agent_name=agent_name,
        full_name=emp['full_name'] if emp and emp['full_name'] else agent_name,
        department=emp['department'] if emp else '',
        role=emp['role'] if emp else '',
        note=emp['note'] if emp else '',
        last_seen_str=format_baku(last_seen),
        is_online=is_online,
        active_window=a['active_window'],
        active_process=a['active_process'],
    )


@main_bp.route('/agent/<agent_name>/gallery')
@login_required
def agent_gallery(agent_name):
    return render_template('gallery.html', agent_name=safe_pc_name(agent_name))
