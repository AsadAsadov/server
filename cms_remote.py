import logging
import platform
import sys
import time

import cms
from agent_remote import LOGGER as REMOTE_LOGGER
from agent_remote import start_remote_control_worker


AGENT_VERSION = "2.1.0-remote-mvp"


def _configure_remote_logging():
    REMOTE_LOGGER.handlers = list(cms._LOGGER.handlers)
    REMOTE_LOGGER.setLevel(logging.INFO)
    REMOTE_LOGGER.propagate = False


def main():
    cms.AGENT_VERSION = AGENT_VERSION
    log_file = cms.setup_logging()
    _configure_remote_logging()

    cms._LOGGER.info("Agent başladılır. Versiya: %s", AGENT_VERSION)
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

    cms._LOGGER.info("Konfiqurasiya: %s", config_path)
    cms._LOGGER.info(
        "Server: %s | PC: %s",
        config["server_url"],
        config["pc_name"],
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
    try:
        remote_worker = start_remote_control_worker(config)
    except Exception:
        cms._LOGGER.exception(
            "Remote control modulu başlaya bilmədi; ekran monitorinqi davam edir"
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
