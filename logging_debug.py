"""Debug logging setup and crash hooks."""

from __future__ import annotations

from collections import deque
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import sys
import threading
import traceback

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # type: ignore


ACTION_RING_MAX = 200
_action_ring: deque[str] = deque(maxlen=ACTION_RING_MAX)


def setup_debug_logging(enabled: bool, log_path: Path) -> logging.Logger | None:
    if not enabled:
        return None
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("gtkv")
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(message)s"
    )
    handler = RotatingFileHandler(
        log_path,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    _install_exception_hooks(logger)
    _install_glib_logger(logger)
    logger.debug("Debug logging enabled: %s", log_path.as_posix())
    return logger


def log_action(message: str) -> None:
    _action_ring.append(message)


def flush_actions(logger: logging.Logger) -> None:
    if not _action_ring:
        return
    logger.debug("Recent actions (newest last):")
    for entry in list(_action_ring):
        logger.debug("  %s", entry)


def _install_exception_hooks(logger: logging.Logger) -> None:
    def _handle_exception(exc_type, exc, tb):
        logger.error("Unhandled exception", exc_info=(exc_type, exc, tb))
        flush_actions(logger)
        _write_traceback_file(exc_type, exc, tb)
        sys.__excepthook__(exc_type, exc, tb)

    def _handle_thread_exception(args):
        logger.error(
            "Unhandled thread exception",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        flush_actions(logger)
        _write_traceback_file(args.exc_type, args.exc_value, args.exc_traceback)

    sys.excepthook = _handle_exception
    threading.excepthook = _handle_thread_exception


def _install_glib_logger(logger: logging.Logger) -> None:
    def _glib_handler(domain, level, message, _userdata):
        level_map = {
            GLib.LogLevelFlags.LEVEL_ERROR: logging.ERROR,
            GLib.LogLevelFlags.LEVEL_CRITICAL: logging.CRITICAL,
            GLib.LogLevelFlags.LEVEL_WARNING: logging.WARNING,
            GLib.LogLevelFlags.LEVEL_MESSAGE: logging.INFO,
            GLib.LogLevelFlags.LEVEL_INFO: logging.INFO,
            GLib.LogLevelFlags.LEVEL_DEBUG: logging.DEBUG,
        }
        py_level = level_map.get(level, logging.INFO)
        logger.log(py_level, "GLib[%s] %s", domain or "", message)
        return False

    GLib.log_set_handler(
        None,
        GLib.LogLevelFlags.LEVEL_ERROR
        | GLib.LogLevelFlags.LEVEL_CRITICAL
        | GLib.LogLevelFlags.LEVEL_WARNING
        | GLib.LogLevelFlags.LEVEL_MESSAGE
        | GLib.LogLevelFlags.LEVEL_INFO
        | GLib.LogLevelFlags.LEVEL_DEBUG,
        _glib_handler,
        None,
    )


def _write_traceback_file(exc_type, exc, tb) -> None:
    try:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        Path("traceback.log").write_text(text, encoding="utf-8")
    except OSError:
        return
