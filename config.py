"""Configuration models for the GTK editor."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppConfig:
    """Runtime configuration for the editor."""

    startup_file: str | None = None
    save_extension: str | None = "gtkv.html"
    cache_max_bytes: int = 200 * 1024 * 1024
    cache_max_files: int = 2000
    cache_max_days: int = 30
    cleanup_cache: bool = False
    show_version: bool = False
    upgrade: bool = False
    debug: bool = False
    font_family: str | None = None
    font_size: int = 11
    tab_width: int = 4
