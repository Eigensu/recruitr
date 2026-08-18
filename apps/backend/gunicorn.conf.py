"""Gunicorn configuration — routes logs by level so log platforms classify correctly.

Railway (like most container platforms) derives severity from the *stream*:
stdout is info, stderr is an error. By default everything lands on stderr —
gunicorn's `errorlog` defaults to "-" (its docs: "Log to stderr by default"),
and uvicorn's default handler is `ext://sys.stderr`. So routine lines like
"Booting worker" and "Application startup complete" get flagged as errors,
and genuine errors become impossible to filter for.

This sends DEBUG/INFO to stdout and WARNING and above to stderr, for
gunicorn, uvicorn and the application's own loggers alike.
"""

import logging
import os


class MaxLevelFilter(logging.Filter):
    """Allow only records strictly below `level` — keeps warnings off stdout."""

    def __init__(self, level: int) -> None:
        super().__init__()
        self.level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self.level


bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("WEB_CONCURRENCY", "4"))
worker_class = "uvicorn.workers.UvicornWorker"
# A worker sends no heartbeat to the master until its lifespan has finished, and
# the lifespan waits on MongoDB. The 30s default is shorter than the database's
# own retry budget, so the master would kill a worker that was still legitimately
# retrying. Keep this above MONGODB_INIT_ATTEMPTS × the per-attempt server
# selection timeout, plus the backoff between attempts (see app/config.py).
timeout = int(os.getenv("WORKER_TIMEOUT", "120"))
accesslog = "-"  # access logs to stdout
errorlog = "-"  # diagnostics to stderr; the dict config below re-routes by level
loglevel = os.getenv("LOG_LEVEL", "info")

_FMT = "%(asctime)s [%(process)d] [%(levelname)s] %(name)s: %(message)s"

logconfig_dict = {
    "version": 1,
    # Leave third-party loggers configured by their own libraries alone.
    "disable_existing_loggers": False,
    "filters": {
        "below_warning": {"()": MaxLevelFilter, "level": logging.WARNING},
    },
    "formatters": {
        "standard": {"format": _FMT},
        # Access lines are already fully formatted by gunicorn/uvicorn.
        "access": {"format": "%(message)s"},
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "standard",
            "filters": ["below_warning"],
        },
        "stderr": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "standard",
            "level": "WARNING",
        },
        "access": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "access",
        },
    },
    "root": {"level": loglevel.upper(), "handlers": ["stdout", "stderr"]},
    "loggers": {
        # Gunicorn's "error" log is really its general diagnostic log.
        "gunicorn.error": {
            "level": loglevel.upper(),
            "handlers": ["stdout", "stderr"],
            "propagate": False,
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["access"],
            "propagate": False,
        },
        "uvicorn": {
            "level": loglevel.upper(),
            "handlers": ["stdout", "stderr"],
            "propagate": False,
        },
        "uvicorn.error": {
            "level": loglevel.upper(),
            "handlers": ["stdout", "stderr"],
            "propagate": False,
        },
        "uvicorn.access": {"level": "INFO", "handlers": ["access"], "propagate": False},
    },
}
