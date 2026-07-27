import logging
import platform
import sys
import time

import agent_remote
import cms
from compact_remote_indicator import CompactRemoteIndicator


REMOTE_AGENT_VERSION = "2.1.3-remote-mvp"
MONITOR_ONLY_VERSION = "2.1.3-monitor-only"
REMOTE_LOGGER = agent_remote.LOGGER


def _configure_remote_logging():
    REMOTE_LOGGER.handlers = list(cms._LOGGER.handlers)
    REMOTE_LOGGER.setLevel(logging.INFO)
    REMOTE_LOGGER.propagate = False


def _start_secure_remote_worker(config, remote_token):
    remote_config = dict(config)
    remote_config["remote_control_token"] = remote_token

    # Keep a small, visible and non-intrusive local safety control.
    agent_remote.RemoteIndicator = CompactRemoteIndicator

    worker = agent_remote.RemoteControlWorker(remote_config)
    worker.http.headers.pop("X-Upload-Token", None)
    worker.http.headers["X-Remote-Token"] = remote_token
    worker.start()
    return worker


def main():
    cms.AGENT_VERSION = REMOTE_AGENT_VERSION
    log_file = cms.setup_logging()
    _configure_remote_logging()

    cms._LOGGER.info("Agent başladılır. Versiya: %s", REMOTE_AGENT_VERSION)
    cms._LOGGER.info(
        "Sistem: %s | Arxitektura: %s",
        platform.platform(),
        platform.machine(),
    )
    cms._LOGGER.info("Log faylı: %s", log_file)

    try:
        config, config_path = cms.load_config()
    except Exception as exc:
        cms._LOGGER.exception("Agent konfiqurasiyası yanlışdır: %s", exc)
        return 2

    remote_enabled = bool(config.get("remote_control_enabled", False))
    remote_token = str(config.get("remote_control_token", "")).strip()
    if not remote_enabled or not remote_token:
        cms.AGENT_VERSION = MONITOR_ONLY_VERSION

    cms._LOGGER.info("Konfiqurasiya: %s", config_path)
    cms._LOGGER.info(
        "Server: %s | PC: %s | Remote: %s",
        config["server_url"],
        config["pc_name"],
        "aktiv" if remote_enabled and remote_token else "deaktiv",
    )

    if not cms.acquire_single_instance(config["pc_name"]):
        cms._LOGGER.warning("Agent artıq işləyir; ikinci instansiya bağlandı")
        return 0

    try:
        screenshot_session = cms.create_http_session()
    except Exception as exc:
        cms._LOGGER.exception("HTTP sessiyası yaradılmadı: %s", exc)
        return 3

    remote_worker = None
    if remote_enabled and remote_token:
        try:
            remote_worker = _start_secure_remote_worker(config, remote_token)
        except Exception:
            cms._LOGGER.exception(
                "Remote control modulu başlaya bilmədi; ekran monitorinqi davam edir"
            )
    elif remote_enabled:
        cms._LOGGER.error(
            "remote_control_enabled aktivdir, amma remote_control_token boşdur"
        )

    metadata_cache = cms.MetadataCache()
    consecutive_failures = 0
    last_success_log_at = 0.0

    try:
        while True:
            started_at = time.monotonic()
            try:
                sent = cms.send_screenshot(
                    screenshot_session,
                    config,
                    metadata_cache,
                )
                if sent:
                    consecutive_failures = 0
                    now = time.time()
                    if now - last_success_log_at >= 300:
                        cms._LOGGER.info(
                            "Agent işləyir və serverə görüntü göndərir"
                        )
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
                cms._LOGGER.info("Agent istifadəçi tərəfindən dayandırıldı")
                break
            except Exception:
                cms._LOGGER.exception("Əsas dövrədə gözlənilməyən xəta")
                time.sleep(5)
    finally:
        if remote_worker:
            remote_worker.stop()
        try:
            screenshot_session.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
