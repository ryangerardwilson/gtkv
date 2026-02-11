"""Visual-mode key handling."""
from __future__ import annotations

from collections.abc import Callable


MoveHandler = Callable[[str, bool], bool]


def handle_key(
    key_name: str,
    on_mode_change: Callable[[str], None],
    on_move: MoveHandler,
) -> bool:
    if key_name == "Escape":
        on_mode_change("normal")
        return True
    if key_name == "v":
        on_mode_change("normal")
        return True
    if key_name in {"h", "j", "k", "l"}:
        on_move(key_name, True)
        return True
    return False
