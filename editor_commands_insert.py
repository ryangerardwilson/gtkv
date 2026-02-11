"""Insert-mode key handling."""
from __future__ import annotations

from collections.abc import Callable


def handle_key(
    key_name: str,
    on_mode_change: Callable[[str], None],
    on_inline_delete: Callable[[str], bool],
) -> bool:
    if key_name == "Escape":
        on_mode_change("normal")
        return True
    if key_name in {"BackSpace", "Delete"}:
        return on_inline_delete(key_name)
    return False
