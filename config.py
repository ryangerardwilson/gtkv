"""User configuration helpers."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path


def get_config_dir() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "gvim"


def get_config_path() -> Path:
    return get_config_dir() / "config.json"


def load_config() -> dict:
    path = get_config_path()
    logging.info("Config path: %s", path)
    if not path.exists():
        logging.info("Config missing")
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logging.error("Config read failed: %s", exc)
        return {}
    raw = raw.lstrip("\ufeff")
    try:
        config = json.loads(raw)
        if isinstance(config, dict):
            logging.info("Config keys: %s", sorted(config.keys()))
        return config
    except json.JSONDecodeError as exc:
        logging.error("Config JSON parse failed: %s", exc)
        return {}


def save_config(config: dict) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")


def get_ui_mode() -> str | None:
    config = load_config()
    value = config.get("mode")
    if isinstance(value, str) and value.strip():
        mode = value.strip().lower()
        logging.info("Config mode: %s", mode)
        return mode
    if value is not None:
        logging.info("Config mode invalid: %r", value)
    return None


def set_ui_mode(mode: str) -> None:
    config = load_config()
    config["mode"] = mode
    save_config(config)


def get_vaults() -> list[Path]:
    config = load_config()
    value = config.get("vaults")
    if not isinstance(value, list):
        return []
    vaults: list[Path] = []
    for entry in value:
        if not isinstance(entry, str):
            continue
        if not entry.strip():
            continue
        vaults.append(Path(entry).expanduser())
    return vaults


def add_vault(vault_path: Path) -> bool:
    config = load_config()
    value = config.get("vaults")
    if isinstance(value, list):
        existing = [path for path in value if isinstance(path, str)]
    else:
        existing = []
    normalized = str(vault_path.expanduser().resolve())
    normalized_existing = {str(Path(path).expanduser().resolve()) for path in existing}
    if normalized in normalized_existing:
        return False
    existing.append(normalized)
    config["vaults"] = existing
    save_config(config)
    return True
