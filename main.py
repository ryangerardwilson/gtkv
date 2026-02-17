"""GTK application entry point."""

from __future__ import annotations

import faulthandler
import logging
import os
import sys
import threading
import traceback
from pathlib import Path
from typing import IO, Sequence

from orchestrator import Orchestrator


def _init_logging() -> tuple[Path, IO[str]]:
    log_path = Path.home() / ".gvim" / "gvim.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_stream = open(log_path, "a", buffering=1, encoding="utf-8")
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)
    faulthandler.enable(file=log_stream, all_threads=True)
    return log_path, log_stream


def _install_exception_hooks() -> None:
    def _log_excepthook(exc_type, exc_value, exc_tb):
        logging.error(
            "Uncaught exception:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    def _thread_excepthook(args):
        logging.error(
            "Unhandled thread exception in %s:\n%s",
            args.thread.name,
            "".join(
                traceback.format_exception(
                    args.exc_type, args.exc_value, args.exc_traceback
                )
            ),
        )

    sys.excepthook = _log_excepthook
    if hasattr(threading, "excepthook"):
        threading.excepthook = _thread_excepthook


def main(argv: Sequence[str] | None = None) -> int:
    log_path, _log_stream = _init_logging()
    _install_exception_hooks()
    logging.info("GVIM start")
    logging.info("Log file: %s", log_path)
    logging.info("Args: %s", list(argv) if argv is not None else sys.argv[1:])
    logging.info("Env DISPLAY=%s WAYLAND_DISPLAY=%s", os.environ.get("DISPLAY"), os.environ.get("WAYLAND_DISPLAY"))
    try:
        return Orchestrator().run(argv)
    except Exception:
        logging.error("Fatal error:\n%s", traceback.format_exc())
        raise


if __name__ == "__main__":
    raise SystemExit(main())
