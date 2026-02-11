"""GTK application entry point."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Sequence

from config import AppConfig
from logging_debug import setup_debug_logging
from _version import __version__

INSTALL_SH_URL = "https://raw.githubusercontent.com/ryangerardwilson/gtkv/main/install.sh"
from orchestrator import Orchestrator


def parse_args(argv: Sequence[str]) -> tuple[AppConfig, list[str]]:
    parser = argparse.ArgumentParser(description="Vim-like GTK editor with image support")
    parser.add_argument("-c", dest="cleanup_cache", action="store_true", help="Clean cache and exit")
    parser.add_argument("-d", "--debug", dest="debug", action="store_true", help="Enable debug logging")
    parser.add_argument("-v", "--version", action="store_true", help="Show installed version")
    parser.add_argument("-u", "--upgrade", action="store_true", help="Upgrade to latest release")
    parser.add_argument("file", nargs="?", help="Optional file to open on startup")
    if hasattr(parser, "parse_known_intermixed_args"):
        args, gtk_args = parser.parse_known_intermixed_args(argv)
    else:
        args, gtk_args = parser.parse_known_args(argv)
    config = AppConfig(
        startup_file=args.file,
        cleanup_cache=args.cleanup_cache,
        show_version=args.version,
        upgrade=args.upgrade,
        debug=args.debug,
    )
    return config, gtk_args


def _run_upgrade() -> int:
    try:
        curl = subprocess.Popen(
            ["curl", "-fsSL", INSTALL_SH_URL],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        print("Upgrade requires curl", file=sys.stderr)
        return 1

    try:
        bash = subprocess.Popen(["bash", "-s", "--", "-u"], stdin=curl.stdout)
        if curl.stdout is not None:
            curl.stdout.close()
    except FileNotFoundError:
        print("Upgrade requires bash", file=sys.stderr)
        curl.terminate()
        curl.wait()
        return 1

    bash_rc = bash.wait()
    curl_rc = curl.wait()

    if curl_rc != 0:
        stderr = (
            curl.stderr.read().decode("utf-8", errors="replace") if curl.stderr else ""
        )
        if stderr:
            sys.stderr.write(stderr)
        return curl_rc

    return bash_rc


def build_application(config: AppConfig):
    import gi  # type: ignore

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk  # type: ignore

    app = Gtk.Application(application_id="com.example.vimgtk")

    def on_activate(application) -> None:
        window = Gtk.ApplicationWindow(application=application)
        window.set_title("Vim GTK")
        window.set_default_size(1024, 768)

        orchestrator = Orchestrator(application=application, window=window, config=config)
        if getattr(config, "cleanup_cache", False):
            orchestrator.cleanup_cache()
            application.quit()
            return
        orchestrator.start()

        window.present()

    app.connect("activate", on_activate)
    return app


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    config, gtk_args = parse_args(args)
    setup_debug_logging(config.debug, Path("debug.log"))
    if config.show_version:
        print(__version__)
        return 0
    if config.upgrade:
        return _run_upgrade()
    app = build_application(config)
    return app.run(gtk_args)


if __name__ == "__main__":
    raise SystemExit(main())
