"""Application logger — loguru with file rotation (10 MB) + console output.

Config-driven via `.env` (loaded by ``config.py``):
  LOG_LEVEL        = DEBUG | INFO | WARNING | ERROR       (default: INFO)
  LOG_FILE         = path to log file                     (default: logs/app.log)
  LOG_MAX_BYTES    = string like "10 MB" or "100 MB"      (default: 10 MB)
  LOG_BACKUP_COUNT = number of backup files to keep       (default: 5)

Usage:
    from app.logger import log

    log.info("ODL response: {}", status)
    log.debug("Topology data: {}", data)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger as _base

import config as cfg

# ── remove default stderr handler so we fully control output ──────────────
_base.remove()


def _log_file_path() -> Path:
    raw = (cfg.settings.log_file or "logs/app.log").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = Path(cfg.PROJECT_ROOT) / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ── file handler with rotation ─────────────────────────────────────────────
_base.add(
    sink=str(_log_file_path()),
    level=cfg.settings.log_level or "INFO",
    rotation=os.getenv("LOG_MAX_BYTES", "10 MB").strip(),
    retention=int(os.getenv("LOG_BACKUP_COUNT", "5")),
    encoding="utf-8",
    enqueue=True,           # thread-safe
    backtrace=False,
    diagnose=False,
    format=(
        "<g>{time:YYYY-MM-DD HH:mm:ss}</g> "
        "<lvl>{level:<7}</lvl> "
        "<c>{name}</c> "
        "{message}"
    ),
)

# ── console handler ────────────────────────────────────────────────────────
_base.add(
    sink=sys.stdout,
    level=cfg.settings.log_level or "INFO",
    colorize=True,
    format=(
        "<g>{time:HH:mm:ss}</g> "
        "<lvl>{level:<7}</lvl> "
        "<c>{name: >18}</c> "
        "{message}"
    ),
)

# ── export a pre-configured logger ─────────────────────────────────────────
log = _base


def shutdown() -> None:
    """Flush and close all handlers (call on app exit)."""
    _base.remove()
