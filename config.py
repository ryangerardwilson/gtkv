"""Configuration models for the GTK editor."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppConfig:
    """Runtime configuration for the editor."""

    theme: str = "default"
    config_path: str | None = None
    startup_file: str | None = None
    file_selector: str = "o"
    save_extension: str | None = "gtkv.html"
    cache_max_bytes: int = 200 * 1024 * 1024
    cache_max_files: int = 2000
    cache_max_days: int = 30
    cleanup_cache: bool = False
    show_version: bool = False
    upgrade: bool = False
