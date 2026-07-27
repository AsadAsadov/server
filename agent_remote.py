import ctypes
import logging
import threading
import time
from ctypes import wintypes
from urllib.parse import urlsplit, urlunsplit

try:
    import requests
except ImportError:
    requests = None


LOGGER = logging.getLogger("BestHomeMonitor.Remote")

if ctypes.sizeof(ctypes.c_void_p) == 8:
    ULONG_PTR = ctypes.c_ulonglong
else:
    ULONG_PTR = ctypes.c_ulong


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION),
    ]


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

VK_KEYS = {
    "BACKSPACE": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "SHIFT": 0x10,
    "CTRL": 0x11,
    "ALT": 0x12,
    "PAUSE": 0x13,
    "CAPSLOCK": 0x14,
    "ESCAPE": 0x1B,
    "SPACE": 0x20,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "END": 0x23,
    "HOME": 0x24,
    "ARROWLEFT": 0x25,
    "ARROWUP": 0x26,
    "ARROWRIGHT": 0x27,
    "ARROWDOWN": 0x28,
    "PRINTSCREEN": 0x2C,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
    "META": 0x5B,
    "CONTEXTMENU": 0x5D,
    "NUMLOCK": 0x90,
    "SCROLLLOCK": 0x91,
    "F1": 0x70,
    "F2": 0x71,
    "F3": 0x72,
    "F4": 0x73,
    "F5": 0x74,
    "F6": 0x75,
    "F7": 0x76,
    "F8": 0x77,
    "F9": 0x78,
    "F10": 0x79,
    "F11": 0x7A,
    "F12": 0x7B,
}


class WindowsInputController(object):
    def __init__(self):
        if not hasattr(ctypes, "windll"):
            raise RuntimeError("Remote control yalnız Windows-da işləyir")
        self.user32 = ctypes.windll.user32
        self.user32.SendInput.argtypes = (
            wintypes.UINT,
            ctypes.POINTER(INPUT),
            ctypes.c_int,
        )
        self.user32.SendInput.restype = wintypes.UINT

    def _send(self, input_value):
        sent = self.user32.SendInput(
            1,
            ctypes.byref(input_value),
            ctypes.sizeof(INPUT),
        )
        if sent != 1:
            raise ctypes.WinError()

    def move(self, x_ratio, y_ratio):
        width = max(int(self.user32.GetSystemMetrics(0)), 1)
        height = max(int(self.user32.GetSystemMetrics(1)), 1)
        x = int(max(0.0, min(1.0, float(x_ratio))) * (width - 1))
        y = int(max(0.0, min(1.0, float(y_ratio))) * (height - 1))
        if not self.user32.SetCursorPos(x, y):
            raise ctypes.WinError()

    def _mouse_flag(self, flag, data=0):
        value = INPUT(
            type=INPUT_MOUSE,
            mi=MOUSEINPUT(
                dx=0,
                dy=0,
                mouseData=ctypes.c_ulong(int(data)).value,
                dwFlags=flag,
                time=0,
                dwExtraInfo=0,
            ),
        )
        self._send(value)

    def click(self, button="left", count=1):
        flags = {
            "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
            "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
            "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
        }
        down_flag, up_flag = flags.get(button, flags["left"])
        for index in range(max(1, min(int(count), 2))):
            self._mouse_flag(down_flag)
            self._mouse_flag(up_flag)
            if index == 0 and count > 1:
                time.sleep(0.08)

    def wheel(self, delta):
        self._mouse_flag(MOUSEEVENTF_WHEEL, int(delta))

    def _key_input(self, virtual_key=0, scan_code=0, flags=0):
        value = INPUT(
            type=INPUT_KEYBOARD,
            ki=KEYBDINPUT(
                wVk=int(virtual_key),
                wScan=int(scan_code),
                dwFlags=int(flags),
                time=0,
                dwExtraInfo=0,
            ),
        )
        self._send(value)

    def _vk_for_key(self, key):
        normalized = str(key or "").upper()
        if normalized in VK_KEYS:
            return VK_KEYS[normalized]
        if len(normalized) == 1:
            value = int(self.user32.VkKeyScanW(ord(normalized)))
            if value != -1:
                return value & 0xFF
        raise ValueError("Dəstəklənməyən düymə: {0}".format(key))

    def key_press(self, key):
        if len(str(key or "")) == 1 and not str(key).isalnum():
            self.text(str(key))
            return
        virtual_key = self._vk_for_key(key)
        self._key_input(virtual_key=virtual_key)
        self._key_input(virtual_key=virtual_key, flags=KEYEVENTF_KEYUP)

    def hotkey(self, keys):
        virtual_keys = [self._vk_for_key(key) for key in keys]
        for virtual_key in virtual_keys:
            self._key_input(virtual_key=virtual_key)
        for virtual_key in reversed(virtual_keys):
            self._key_input(virtual_key=virtual_key, flags=KEYEVENTF_KEYUP)

    def text(self, text):
        encoded = str(text).encode("utf-16-le")
        for index in range(0, len(encoded), 2):
            code_unit = encoded[index] | (encoded[index + 1] << 8)
            self._key_input(scan_code=code_unit, flags=KEYEVENTF_UNICODE)
            self._key_input(
                scan_code=code_unit,
                flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
            )

    def execute(self, command):
        command_type = command.get("type")
        payload = command.get("payload") or {}
        if command_type == "move":
            self.move(payload.get("x", 0), payload.get("y", 0))
        elif command_type == "click":
            self.click(payload.get("button", "left"), payload.get("count", 1))
        elif command_type == "wheel":
            self.wheel(payload.get("delta", 0))
        elif command_type == "text":
            self.text(payload.get("text", ""))
        elif command_type == "key":
            self.key_press(payload.get("key", ""))
        elif command_type == "hotkey":
            self.hotkey(payload.get("keys") or [])
        else:
            raise ValueError("Naməlum remote komanda: {0}".format(command_type))


class RemoteIndicator(object):
    def __init__(self, pc_name):
        self.pc_name = pc_name
        self.close_event = threading.Event()
        self.user_stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.close_event.clear()
        self.user_stop_event.clear()
        self.thread = threading.Thread(
            target=self._run,
            name="BestHomeRemoteIndicator",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.close_event.set()

    def _run(self):
        try:
            import tkinter as tk

            root = tk.Tk()
            root.title("BestHome Monitor - Remote Control")
            root.configure(bg="#7f1d1d")
            root.attributes("-topmost", True)
            root.resizable(False, False)
            width = 390
            height = 135
            screen_width = root.winfo_screenwidth()
            root.geometry(
                "{0}x{1}+{2}+20".format(
                    width,
                    height,
                    max(screen_width - width - 24, 0),
                )
            )

            def user_stop():
                self.user_stop_event.set()
                self.close_event.set()

            root.protocol("WM_DELETE_WINDOW", user_stop)
            tk.Label(
                root,
                text="UZAQDAN İDARƏETMƏ AKTİVDİR",
                bg="#7f1d1d",
                fg="white",
                font=("Segoe UI", 11, "bold"),
            ).pack(pady=(18, 4))
            tk.Label(
                root,
                text="Administrator bu kompüterdə mouse və klaviaturadan istifadə edir.",
                bg="#7f1d1d",
                fg="#fee2e2",
                font=("Segoe UI", 9),
                wraplength=350,
            ).pack()
            tk.Button(
                root,
                text="İdarəetməni dayandır",
                command=user_stop,
                bg="#ffffff",
                fg="#7f1d1d",
                relief="flat",
                font=("Segoe UI", 9, "bold"),
                padx=14,
                pady=5,
            ).pack(pady=12)

            def check_close():
                if self.close_event.is_set():
                    root.destroy()
                    return
                root.after(250, check_close)

            root.after(250, check_close)
            root.mainloop()
        except Exception:
            LOGGER.exception("Remote idarəetmə göstəricisi açıla bilmədi")


def _api_url(server_url, path):
    parsed = urlsplit(server_url)
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _request_consent(pc_name):
    flags = 0x00000004 | 0x00000030 | 0x00040000 | 0x00010000
    message = (
        "BestHome Monitor administratoru bu kompüteri uzaqdan idarə etmək istəyir.\n\n"
        "İcazə verdikdə administrator mouse və klaviaturadan istifadə edə biləcək.\n"
        "İdarəetmə zamanı ekranda daimi xəbərdarlıq görünəcək."
    )
    result = ctypes.windll.user32.MessageBoxW(
        None,
        message,
        "Uzaqdan idarəetmə icazəsi - {0}".format(pc_name),
        flags,
    )
    return result == 6


class RemoteControlWorker(object):
    def __init__(self, config):
        if requests is None:
            raise RuntimeError("requests kitabxanası mövcud deyil")
        self.config = config
        self.pc_name = config["pc_name"]
        self.enabled = bool(config.get("remote_control_enabled", False))
        self.mode = str(config.get("remote_control_mode", "ask")).lower()
        self.poll_interval = max(
            0.1,
            float(config.get("remote_poll_interval_seconds", 0.15)),
        )
        self.poll_url = _api_url(config["server_url"], "/api/agent/remote/poll")
        self.state_url = _api_url(config["server_url"], "/api/agent/remote/state")
        self.stop_event = threading.Event()
        self.thread = None
        self.http = requests.Session()
        self.http.headers.update(
            {
                "User-Agent": "BestHomeMonitorRemote/1.0",
                "X-Upload-Token": config["upload_token"],
            }
        )
        self.current_session_id = None
        self.current_accepted = False
        self.indicator = None
        self.controller = WindowsInputController()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(
            target=self._run,
            name="BestHomeRemoteControl",
            daemon=True,
        )
        self.thread.start()
        LOGGER.info(
            "Remote control worker başladı. enabled=%s mode=%s",
            self.enabled,
            self.mode,
        )

    def stop(self):
        self.stop_event.set()
        self._clear_local_session()
        try:
            self.http.close()
        except Exception:
            pass

    def _post_state(self, session_id, state, message=""):
        try:
            response = self.http.post(
                self.state_url,
                json={
                    "pc_name": self.pc_name,
                    "session_id": session_id,
                    "state": state,
                    "message": message,
                },
                timeout=(3, 5),
                verify=self.config.get("verify_tls", True),
            )
            if response.status_code >= 400:
                LOGGER.warning(
                    "Remote state HTTP %s: %s",
                    response.status_code,
                    response.text[:200],
                )
                return False
            return True
        except Exception as exc:
            LOGGER.warning("Remote status göndərilmədi: %s", exc)
            return False

    def _clear_local_session(self):
        if self.indicator:
            self.indicator.stop()
        self.indicator = None
        self.current_session_id = None
        self.current_accepted = False

    def _accept_or_deny(self, session_id):
        if not self.enabled:
            self._post_state(session_id, "denied", "Remote control agent config-də deaktivdir")
            return False

        accepted = self.mode == "unattended"
        if self.mode != "unattended":
            accepted = _request_consent(self.pc_name)

        if not accepted:
            self._post_state(session_id, "denied", "İstifadəçi icazə vermədi")
            return False

        if not self._post_state(session_id, "accepted", "İdarəetmə icazəsi verildi"):
            return False

        self.current_session_id = session_id
        self.current_accepted = True
        self.indicator = RemoteIndicator(self.pc_name)
        self.indicator.start()
        LOGGER.info("Remote idarəetmə sessiyası qəbul edildi: %s", session_id)
        return True

    def _execute_commands(self, commands):
        for command in commands:
            try:
                self.controller.execute(command)
            except Exception:
                LOGGER.exception("Remote komanda icra olunmadı: %r", command)

    def _run(self):
        while not self.stop_event.is_set():
            try:
                response = self.http.post(
                    self.poll_url,
                    json={"pc_name": self.pc_name},
                    timeout=(3, 5),
                    verify=self.config.get("verify_tls", True),
                )
                if response.status_code >= 400:
                    LOGGER.warning(
                        "Remote poll HTTP %s: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    time.sleep(2)
                    continue

                data = response.json()
                remote_session = data.get("session")
                commands = data.get("commands") or []

                if not remote_session:
                    if self.current_session_id:
                        LOGGER.info("Remote sessiya server tərəfindən bağlandı")
                    self._clear_local_session()
                    time.sleep(0.5)
                    continue

                session_id = remote_session.get("id")
                status = remote_session.get("status")

                if self.current_session_id and self.current_session_id != session_id:
                    self._clear_local_session()

                if status == "pending" and self.current_session_id != session_id:
                    if not self._accept_or_deny(session_id):
                        time.sleep(0.5)
                        continue

                if status == "active":
                    if self.current_session_id != session_id:
                        self.current_session_id = session_id
                        self.current_accepted = True
                        self.indicator = RemoteIndicator(self.pc_name)
                        self.indicator.start()
                    if self.indicator and self.indicator.user_stop_event.is_set():
                        self._post_state(session_id, "stopped", "İstifadəçi idarəetməni dayandırdı")
                        self._clear_local_session()
                        time.sleep(0.5)
                        continue
                    self._execute_commands(commands)
                elif status == "ended":
                    self._clear_local_session()

                time.sleep(self.poll_interval)
            except Exception as exc:
                LOGGER.warning("Remote poll bağlantı xətası: %s", exc)
                time.sleep(2)



def start_remote_control_worker(config):
    worker = RemoteControlWorker(config)
    worker.start()
    return worker
