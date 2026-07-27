import io
import json
import logging
import os
import platform
import socket
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

try:
    import requests
except ImportError:
    requests = None

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

try:
    import win32api
except ImportError:
    win32api = None

try:
    import win32gui
    import win32process
except ImportError:
    win32gui = None
    win32process = None

try:
    from pywinauto import Desktop
except ImportError:
    Desktop = None


AGENT_VERSION = "2.0.0"
DEFAULT_CONFIG = {
    "server_url": "https://monitor.besthome.az/upload",
    "upload_token": "",
    "pc_name": "",
    "screen_interval_seconds": 0.5,
    "request_timeout_seconds": 10,
    "jpeg_quality": 40,
    "process_refresh_seconds": 15,
    "browser_url_refresh_seconds": 5,
    "max_retry_seconds": 30,
    "verify_tls": True,
}
BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
}
ERROR_ALREADY_EXISTS = 183

_LOGGER = logging.getLogger("BestHomeMonitor")
_LAST_LOG_TIMES = {}
_SINGLE_INSTANCE_HANDLE = None


def application_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def writable_data_dir():
    candidates = []
    program_data = os.environ.get("PROGRAMDATA")
    all_users_profile = os.environ.get("ALLUSERSPROFILE")
    if program_data:
        candidates.append(Path(program_data) / "BestHomeMonitor")
    if all_users_profile:
        candidates.append(Path(all_users_profile) / "BestHomeMonitor")
    candidates.append(application_dir() / "data")

    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            test_file = path / ".write-test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
            return path
        except Exception:
            continue
    return application_dir()


def setup_logging():
    log_dir = writable_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent.log"

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    file_handler = RotatingFileHandler(
        str(log_file),
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    _LOGGER.handlers = [file_handler]
    _LOGGER.setLevel(logging.INFO)
    _LOGGER.propagate = False
    return log_file


def log_throttled(key, level, message, interval_seconds=60):
    now = time.time()
    previous = _LAST_LOG_TIMES.get(key, 0)
    if now - previous < interval_seconds:
        return
    _LAST_LOG_TIMES[key] = now
    _LOGGER.log(level, message)


def load_config():
    config = dict(DEFAULT_CONFIG)
    config_path = Path(
        os.environ.get(
            "BESTHOME_MONITOR_CONFIG",
            str(application_dir() / "agent_config.json"),
        )
    )

    if config_path.exists():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
            else:
                raise ValueError("Konfiqurasiya JSON obyekti olmalıdır")
        except Exception as exc:
            raise RuntimeError(
                "Konfiqurasiya faylı oxunmadı: {0} ({1})".format(
                    config_path, exc
                )
            )

    environment_overrides = {
        "server_url": os.environ.get("BESTHOME_MONITOR_SERVER_URL"),
        "upload_token": os.environ.get("BESTHOME_MONITOR_UPLOAD_TOKEN"),
        "pc_name": os.environ.get("BESTHOME_MONITOR_PC_NAME"),
    }
    for key, value in environment_overrides.items():
        if value:
            config[key] = value

    config["server_url"] = str(config.get("server_url", "")).strip()
    config["upload_token"] = str(config.get("upload_token", "")).strip()
    config["pc_name"] = (
        str(config.get("pc_name", "")).strip() or socket.gethostname()
    )
    config["screen_interval_seconds"] = max(
        0.25, float(config.get("screen_interval_seconds", 0.5))
    )
    config["request_timeout_seconds"] = max(
        2, int(config.get("request_timeout_seconds", 10))
    )
    config["jpeg_quality"] = min(
        90, max(20, int(config.get("jpeg_quality", 40)))
    )
    config["process_refresh_seconds"] = max(
        5, int(config.get("process_refresh_seconds", 15))
    )
    config["browser_url_refresh_seconds"] = max(
        2, int(config.get("browser_url_refresh_seconds", 5))
    )
    config["max_retry_seconds"] = max(
        5, int(config.get("max_retry_seconds", 30))
    )
    config["verify_tls"] = bool(config.get("verify_tls", True))

    if not config["server_url"].startswith(("http://", "https://")):
        raise RuntimeError("server_url düzgün HTTP/HTTPS ünvanı deyil")
    if not config["upload_token"]:
        raise RuntimeError(
            "upload_token boşdur. agent_config.json faylını doldur."
        )
    return config, config_path


def acquire_single_instance(pc_name):
    global _SINGLE_INSTANCE_HANDLE
    try:
        import ctypes

        mutex_name = "Local\\BestHomeMonitorAgent_{0}".format(pc_name)
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        if not handle:
            return True
        _SINGLE_INSTANCE_HANDLE = handle
        return ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS
    except Exception as exc:
        log_throttled(
            "single-instance",
            logging.WARNING,
            "Tək instansiya yoxlaması işləmədi: {0}".format(exc),
            300,
        )
        return True


def take_screenshot():
    if ImageGrab is None:
        log_throttled(
            "missing-imagegrab",
            logging.ERROR,
            "Pillow ImageGrab mövcud deyil",
            300,
        )
        return None

    try:
        try:
            image = ImageGrab.grab(all_screens=True)
        except TypeError:
            image = ImageGrab.grab()
        if image.mode != "RGB":
            image = image.convert("RGB")
        return image
    except Exception as exc:
        log_throttled(
            "screenshot-failed",
            logging.ERROR,
            "Ekran görüntüsü alınmadı: {0}".format(exc),
            30,
        )
        return None


def get_active_window_info():
    if win32gui is None or win32process is None:
        return "", ""

    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return "", ""
        title = win32gui.GetWindowText(hwnd) or ""
        _thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
        process_name = "UNKNOWN"
        if psutil is not None:
            try:
                process_name = psutil.Process(process_id).name()
            except (psutil.Error, OSError):
                process_name = "UNKNOWN"
        return title, process_name
    except Exception as exc:
        log_throttled(
            "active-window-failed",
            logging.WARNING,
            "Aktiv pəncərə məlumatı alınmadı: {0}".format(exc),
            60,
        )
        return "", ""


def get_mouse_info():
    if win32api is None:
        return None, None, None, None

    try:
        mouse_x, mouse_y = win32api.GetCursorPos()
        screen_width = win32api.GetSystemMetrics(0)
        screen_height = win32api.GetSystemMetrics(1)
        return mouse_x, mouse_y, screen_width, screen_height
    except Exception as exc:
        log_throttled(
            "mouse-info-failed",
            logging.WARNING,
            "Siçan məlumatı alınmadı: {0}".format(exc),
            60,
        )
        return None, None, None, None


def get_running_processes():
    if psutil is None:
        return ""

    names = set()
    try:
        for process in psutil.process_iter(["name"]):
            try:
                name = process.info.get("name")
                if name:
                    names.add(name)
            except (psutil.Error, OSError):
                continue
    except Exception as exc:
        log_throttled(
            "process-list-failed",
            logging.WARNING,
            "Proses siyahısı alınmadı: {0}".format(exc),
            60,
        )
    return ",".join(sorted(names, key=str.lower))


def get_active_browser_url(active_process):
    process_name = (active_process or "").lower()
    if process_name not in BROWSER_PROCESSES:
        return ""
    if Desktop is None or win32gui is None:
        return ""

    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return ""

        window = Desktop(backend="uia").window(handle=hwnd)
        for control in window.descendants(control_type="Edit"):
            try:
                active_url = control.get_value()
            except Exception:
                try:
                    active_url = control.window_text()
                except Exception:
                    active_url = ""

            active_url = (active_url or "").strip()
            if active_url.startswith(("http://", "https://")):
                return active_url
    except Exception as exc:
        log_throttled(
            "browser-url-failed",
            logging.WARNING,
            "Brauzer URL-i alınmadı: {0}".format(exc),
            120,
        )
    return ""


def form_value(value):
    if value is None:
        return ""
    return str(value)


class MetadataCache(object):
    def __init__(self):
        self.process_list = ""
        self.process_updated_at = 0.0
        self.active_url = ""
        self.url_process = ""
        self.url_updated_at = 0.0

    def collect(self, config):
        now = time.monotonic()
        active_title, active_process = get_active_window_info()

        if now - self.process_updated_at >= config["process_refresh_seconds"]:
            self.process_list = get_running_processes()
            self.process_updated_at = now

        current_process = (active_process or "").lower()
        if current_process not in BROWSER_PROCESSES:
            self.active_url = ""
            self.url_process = current_process
            self.url_updated_at = now
        elif (
            current_process != self.url_process
            or now - self.url_updated_at
            >= config["browser_url_refresh_seconds"]
        ):
            self.active_url = get_active_browser_url(active_process)
            self.url_process = current_process
            self.url_updated_at = now

        mouse_x, mouse_y, screen_width, screen_height = get_mouse_info()
        return {
            "active_window": active_title or "",
            "active_process": active_process or "",
            "process_list": self.process_list,
            "mouse_x": form_value(mouse_x),
            "mouse_y": form_value(mouse_y),
            "screen_width": form_value(screen_width),
            "screen_height": form_value(screen_height),
            "active_url": self.active_url,
        }


def create_http_session():
    if requests is None:
        raise RuntimeError("requests kitabxanası mövcud deyil")

    session = requests.Session()
    session.headers.update(
        {"User-Agent": "BestHomeMonitorAgent/{0}".format(AGENT_VERSION)}
    )
    return session


def send_screenshot(session, config, metadata_cache):
    image = take_screenshot()
    if image is None:
        return False

    buffer = io.BytesIO()
    try:
        image.save(
            buffer,
            format="JPEG",
            quality=config["jpeg_quality"],
            optimize=True,
        )
        buffer.seek(0)

        data = metadata_cache.collect(config)
        data.update(
            {
                "pc_name": config["pc_name"],
                "agent_version": AGENT_VERSION,
            }
        )
        files = {
            "screenshot": (
                "screen.jpg",
                buffer,
                "image/jpeg",
            )
        }
        response = session.post(
            config["server_url"],
            data=data,
            files=files,
            headers={"X-Upload-Token": config["upload_token"]},
            timeout=(5, config["request_timeout_seconds"]),
            verify=config["verify_tls"],
        )

        if response.status_code == 401:
            log_throttled(
                "upload-unauthorized",
                logging.ERROR,
                "Server upload tokenini qəbul etmədi (401)",
                60,
            )
            return False
        if response.status_code >= 400:
            log_throttled(
                "upload-http-error-{0}".format(response.status_code),
                logging.ERROR,
                "Server HTTP {0} qaytardı: {1}".format(
                    response.status_code,
                    response.text[:200],
                ),
                30,
            )
            return False
        return True
    except requests.exceptions.SSLError as exc:
        log_throttled(
            "upload-ssl-error",
            logging.ERROR,
            "SSL xətası: {0}".format(exc),
            60,
        )
        return False
    except requests.exceptions.Timeout:
        log_throttled(
            "upload-timeout",
            logging.WARNING,
            "Serverə göndəriş vaxtı bitdi",
            30,
        )
        return False
    except requests.exceptions.ConnectionError as exc:
        log_throttled(
            "upload-connection-error",
            logging.WARNING,
            "Server bağlantısı yoxdur: {0}".format(exc),
            30,
        )
        return False
    except requests.exceptions.RequestException as exc:
        log_throttled(
            "upload-request-error",
            logging.ERROR,
            "Göndəriş xətası: {0}".format(exc),
            30,
        )
        return False
    except Exception:
        _LOGGER.exception("Gözlənilməyən agent xətası")
        return False
    finally:
        try:
            image.close()
        except Exception:
            pass
        buffer.close()


def main():
    log_file = setup_logging()
    _LOGGER.info("Agent başladılır. Versiya: %s", AGENT_VERSION)
    _LOGGER.info(
        "Sistem: %s | Arxitektura: %s",
        platform.platform(),
        platform.machine(),
    )
    _LOGGER.info("Log faylı: %s", log_file)

    try:
        config, config_path = load_config()
    except Exception as exc:
        _LOGGER.exception("Agent konfiqurasiyası yanlışdır: %s", exc)
        return 2

    _LOGGER.info("Konfiqurasiya: %s", config_path)
    _LOGGER.info("Server: %s | PC: %s", config["server_url"], config["pc_name"])

    if not acquire_single_instance(config["pc_name"]):
        _LOGGER.warning("Agent artıq işləyir; ikinci instansiya bağlandı")
        return 0

    try:
        session = create_http_session()
    except Exception as exc:
        _LOGGER.exception("HTTP sessiyası yaradılmadı: %s", exc)
        return 3

    metadata_cache = MetadataCache()
    consecutive_failures = 0
    last_success_log_at = 0.0

    while True:
        started_at = time.monotonic()
        try:
            sent = send_screenshot(session, config, metadata_cache)
            if sent:
                consecutive_failures = 0
                now = time.time()
                if now - last_success_log_at >= 300:
                    _LOGGER.info("Agent işləyir və serverə görüntü göndərir")
                    last_success_log_at = now
                elapsed = time.monotonic() - started_at
                time.sleep(
                    max(
                        0.05,
                        config["screen_interval_seconds"] - elapsed,
                    )
                )
            else:
                consecutive_failures += 1
                retry_delay = min(
                    config["max_retry_seconds"],
                    max(1, 2 ** min(consecutive_failures - 1, 5)),
                )
                time.sleep(retry_delay)
        except KeyboardInterrupt:
            _LOGGER.info("Agent istifadəçi tərəfindən dayandırıldı")
            break
        except Exception:
            _LOGGER.exception("Əsas dövrədə gözlənilməyən xəta")
            time.sleep(5)

    try:
        session.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
