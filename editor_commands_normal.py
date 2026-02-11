"""Normal-mode key handling."""
from __future__ import annotations

from collections.abc import Callable


MoveHandler = Callable[[str, bool], bool]


def handle_key(
    key_name: str,
    on_mode_change: Callable[[str], None],
    on_move: MoveHandler,
) -> bool:
    if key_name == "i":
        on_mode_change("insert")
        return True
    if key_name == "v":
        on_mode_change("visual")
        return True
    if key_name in {"h", "j", "k", "l"}:
        on_move(key_name, False)
        return True
    return False
