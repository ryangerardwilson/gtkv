"""Normal-mode key handling."""
from __future__ import annotations

from collections.abc import Callable


def handle_key(key_name: str, on_mode_change: Callable[[str], None]) -> bool:
    if key_name == "i":
        on_mode_change("insert")
        return True
    return False
