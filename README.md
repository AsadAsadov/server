# BestHome Monitor Server

Professional Flask layout for the existing internal employee-computer monitoring server. Screenshot images are RAM-only; `monitor.db` keeps agent/metadata rows, but uploaded JPEG bytes are not written to `screens/`.

## Project structure

```text
app.py                 # Flask application factory and logging setup
server.py              # Backward-compatible local entrypoint
wsgi.py                # Gunicorn entrypoint
config.py              # .env-backed configuration
database.py            # SQLite connection, tables, WAL, indexes
auth.py                # Login/logout and auth decorator
routes/                # Dashboard, upload, screenshot, and API routes
services/cleanup.py    # RAM screenshot and DB metadata cleanup
services/ram_screens.py # Thread-safe in-memory screenshot store
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
UPLOAD_FOLDER=screens  # legacy only; not used for file writes
DB_PATH=monitor.db
KEEP_MINUTES=60
MAX_RAM_SHOTS_PER_AGENT=300
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

1. Copy the project to `/opt/besthome-monitor` without deleting existing `monitor.db`. The `screens/` directory is no longer required for new uploads.
2. Create a virtual environment and install dependencies:
   ```bash
   cd /opt/besthome-monitor
   python3 -m venv venv
   . venv/bin/activate
   pip install -r requirements.txt
   ```
3. Set strong values in `/opt/besthome-monitor/.env`.
4. Copy `deployment/besthome-monitor.service` to `/etc/systemd/system/besthome-monitor.service` and adjust `User`, `Group`, and paths if needed. Keep Gunicorn at `--workers 1`; RAM-only screenshots are process-local and multiple workers would have separate stores.
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
- Uploads store JPEG bytes in a thread-safe RAM store keyed by virtual filename; `/screens/<filename>` serves `send_file(io.BytesIO(...), mimetype="image/jpeg")`.
- Cleanup removes RAM screenshots older than `KEEP_MINUTES`, caps each agent at `MAX_RAM_SHOTS_PER_AGENT`, and deletes old screenshot metadata rows from SQLite.
- Server restart clears screenshots by design. Agents will repopulate RAM on the next upload.
- Gunicorn must run with `--workers 1` in RAM-only mode because worker memory is not shared across processes.
