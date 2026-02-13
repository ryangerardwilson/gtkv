"""User configuration helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path


def get_config_dir() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "gtkv"


def get_config_path() -> Path:
    return get_config_dir() / "config.json"


def load_config() -> dict:
    path = get_config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(config: dict) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")


def get_python_path() -> str | None:
    config = load_config()
    value = config.get("python_path")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def set_python_path(python_path: str) -> None:
    config = load_config()
    config["python_path"] = python_path
    save_config(config)
