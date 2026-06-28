import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta
from pathlib import Path
from flask import Flask
from auth import auth_bp
from config import Config
from database import init_db
from routes.api import api_bp
from routes.main import main_bp
from routes.upload import upload_bp
from utils.security import generate_csrf_token


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = app.config['SECRET_KEY']
    app.permanent_session_lifetime = timedelta(minutes=app.config['PERMANENT_SESSION_LIFETIME_MINUTES'])

    Path('logs').mkdir(exist_ok=True)
    _configure_logging(app)

    init_db()
    app.jinja_env.globals['csrf_token'] = generate_csrf_token
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(upload_bp)
    return app


def _configure_logging(app):
    formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=2_000_000, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.WARNING)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])
    app.logger.handlers = [file_handler, stream_handler]
    app.logger.setLevel(logging.INFO)


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=False)
