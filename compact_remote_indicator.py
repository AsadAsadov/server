import logging
import threading


LOGGER = logging.getLogger("BestHomeMonitor.Remote")


class CompactRemoteIndicator(object):
    """Small visible remote-control badge with a minimal local stop control."""

    BADGE_SIZE = 32
    PANEL_WIDTH = 126
    PANEL_HEIGHT = 42
    EDGE_GAP = 14
    BOTTOM_GAP = 72
    TRANSPARENT_KEY = "#010203"

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
            name="BestHomeCompactRemoteIndicator",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.close_event.set()

    def _run(self):
        try:
            import tkinter as tk

            root = tk.Tk()
            root.title("BestHome Monitor")
            root.configure(bg=self.TRANSPARENT_KEY)
            root.overrideredirect(True)
            root.attributes("-topmost", True)

            try:
                root.attributes("-transparentcolor", self.TRANSPARENT_KEY)
            except Exception:
                pass

            try:
                root.attributes("-alpha", 0.72)
            except Exception:
                pass

            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            badge_x = max(
                screen_width - self.BADGE_SIZE - self.EDGE_GAP,
                0,
            )
            badge_y = max(
                screen_height - self.BADGE_SIZE - self.BOTTOM_GAP,
                0,
            )

            root.geometry(
                "{0}x{0}+{1}+{2}".format(
                    self.BADGE_SIZE,
                    badge_x,
                    badge_y,
                )
            )

            canvas = tk.Canvas(
                root,
                width=self.BADGE_SIZE,
                height=self.BADGE_SIZE,
                bg=self.TRANSPARENT_KEY,
                highlightthickness=0,
                borderwidth=0,
                cursor="hand2",
            )
            canvas.pack(fill="both", expand=True)

            canvas.create_oval(
                2,
                2,
                self.BADGE_SIZE - 2,
                self.BADGE_SIZE - 2,
                fill="#e5e7eb",
                outline="#ffffff",
                width=1,
            )
            canvas.create_text(
                self.BADGE_SIZE // 2,
                self.BADGE_SIZE // 2,
                text="BH",
                fill="#374151",
                font=("Segoe UI", 8, "bold"),
            )

            panel_holder = {"window": None}

            def close_panel():
                panel = panel_holder.get("window")
                if panel is not None:
                    try:
                        panel.destroy()
                    except Exception:
                        pass
                panel_holder["window"] = None

            def user_stop():
                self.user_stop_event.set()
                self.close_event.set()
                close_panel()
                try:
                    root.destroy()
                except Exception:
                    pass

            def open_panel():
                existing = panel_holder.get("window")
                if existing is not None:
                    close_panel()
                    return

                panel = tk.Toplevel(root)
                panel_holder["window"] = panel
                panel.title("BestHome Monitor")
                panel.configure(bg="#111827")
                panel.overrideredirect(True)
                panel.attributes("-topmost", True)

                try:
                    panel.attributes("-alpha", 0.88)
                except Exception:
                    pass

                panel_x = max(
                    screen_width - self.PANEL_WIDTH - self.EDGE_GAP,
                    0,
                )
                panel_y = max(
                    badge_y - self.PANEL_HEIGHT - 8,
                    0,
                )

                panel.geometry(
                    "{0}x{1}+{2}+{3}".format(
                        self.PANEL_WIDTH,
                        self.PANEL_HEIGHT,
                        panel_x,
                        panel_y,
                    )
                )

                tk.Button(
                    panel,
                    text="Dayandır",
                    command=user_stop,
                    bg="#f3f4f6",
                    fg="#111827",
                    activebackground="#e5e7eb",
                    activeforeground="#111827",
                    relief="flat",
                    borderwidth=0,
                    font=("Segoe UI", 9, "bold"),
                    cursor="hand2",
                ).pack(fill="both", expand=True, padx=6, pady=6)

            canvas.bind("<Button-1>", lambda _event: open_panel())
            canvas.bind("<Button-3>", lambda _event: open_panel())

            def check_close():
                if self.close_event.is_set():
                    close_panel()
                    try:
                        root.destroy()
                    except Exception:
                        pass
                    return
                root.after(250, check_close)

            root.after(250, check_close)
            root.mainloop()
        except Exception:
            LOGGER.exception("Kompakt remote göstəricisi açıla bilmədi")
