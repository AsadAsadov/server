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
        ],
    )
    print("REMOTE MOBILE ASSETS: OK")


if __name__ == "__main__":
    main()
