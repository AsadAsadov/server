# BestHome Monitor Server

Professional Flask layout for the existing internal employee-computer monitoring server. Existing routes, `monitor.db`, and the `screens/` folder are preserved.

## Project structure

```text
app.py                 # Flask application factory and logging setup
server.py              # Backward-compatible local entrypoint
wsgi.py                # Gunicorn entrypoint
config.py              # .env-backed configuration
database.py            # SQLite connection, tables, WAL, indexes
auth.py                # Login/logout and auth decorator
routes/                # Dashboard, upload, screenshot, and API routes
services/cleanup.py    # Old screenshot and DB-record cleanup
utils/security.py      # CSRF, token, filename, and pc-name helpers
templates/             # Jinja templates
static/css/style.css   # Extracted CSS
logs/app.log           # Runtime log file
deployment/            # systemd and nginx examples
```

## Environment

Create/update `.env`:

```env
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-me
SECRET_KEY=replace-with-long-random-secret
UPLOAD_FOLDER=screens
DB_PATH=monitor.db
KEEP_MINUTES=10
UPLOAD_TOKEN=replace-with-long-random-upload-token
```

Agents must send the upload token in `X-Upload-Token`, `upload_token` form field, or `token` query parameter.

## Local run

```bash
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
python server.py
```

Open `http://127.0.0.1:5050/login`.

## VPS deployment

1. Copy the project to `/opt/besthome-monitor` without deleting existing `monitor.db` or `screens/`.
2. Create a virtual environment and install dependencies:
   ```bash
   cd /opt/besthome-monitor
   python3 -m venv venv
   . venv/bin/activate
   pip install -r requirements.txt
   ```
3. Set strong values in `/opt/besthome-monitor/.env`.
4. Copy `deployment/besthome-monitor.service` to `/etc/systemd/system/besthome-monitor.service` and adjust `User`, `Group`, and paths if needed.
5. Enable the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now besthome-monitor
   sudo systemctl status besthome-monitor
   ```
6. Copy `deployment/nginx.conf` to `/etc/nginx/sites-available/besthome-monitor`, link it into `sites-enabled`, update `server_name`, then reload nginx:
   ```bash
   sudo ln -s /etc/nginx/sites-available/besthome-monitor /etc/nginx/sites-enabled/besthome-monitor
   sudo nginx -t
   sudo systemctl reload nginx
   ```
7. For HTTPS, install a TLS certificate, then set `SESSION_COOKIE_SECURE=1` in `.env`.

## Notes

- `debug=False` is kept for production.
- SQLite WAL mode and indexes are initialized automatically.
- Cleanup deletes old archive files and their `screenshots` rows, but keeps live `*_last.jpg` files.
