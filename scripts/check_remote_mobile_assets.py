from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(path, snippets):
    text = (ROOT / path).read_text(encoding="utf-8")
    for snippet in snippets:
        if snippet not in text:
            raise AssertionError("Missing {0!r} in {1}".format(snippet, path))


def main():
    require(
        "templates/agent_remote.html",
        [
            "remote-control-mobile.css",
            "mobile-keyboard-button",
            "mobile-exit-button",
            "mobile-keyboard-input",
            "remote-control-mobile.js",
        ],
    )
    require(
        "static/css/remote-control-mobile.css",
        [
            "100dvh",
            ".mobile-remote-toolbar",
            ".mouse-cursor",
            ".remote-active-banner",
            "body.remote-page.focus-mode .mobile-remote-toolbar",
            "focus-mode:not(.remote-control-active) #mobile-keyboard-button",
        ],
    )
    require(
        "static/js/remote-control-mobile.js",
        [
            "touchstart",
            "touchmove",
            "touchend",
            "beforeinput",
            "KeyboardEvent",
            "MouseEvent",
            "autoFocusedForSession",
            "TRACKPAD_SPEED",
            "virtualCursor",
            "moveVirtualCursor",
            "keepKeyboardOpen",
        ],
    )
    print("REMOTE MOBILE ASSETS: OK")


if __name__ == "__main__":
    main()
