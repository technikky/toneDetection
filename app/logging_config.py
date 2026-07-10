"""Stage 15: structured local error/crash logging -- no cloud dependency.

Writes a rotating log file locally so that when the app misbehaves on a
school computer, a teacher (or whoever supports them) can grab
app/data/logs/app.log and send it along, rather than having to describe
whatever flashed by in a console window that's since closed.

To wire in a crash-reporting SaaS (Sentry or similar) later: install its
SDK, call its init() here behind an opt-in env var (e.g. only if
SIGHTSINGING_SENTRY_DSN is set), and leave everything below unchanged --
this module's job is just to guarantee there's always a local record,
whether or not a remote one also exists.
"""
import logging
import logging.handlers
import sys

from app.config import LOGS_DIR

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
LOG_FILE = LOGS_DIR / "app.log"

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    formatter = logging.Formatter(LOG_FORMAT)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    logging.getLogger("sight_singing").info("Logging configured -- writing to %s", LOG_FILE)
