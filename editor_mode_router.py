"""Mode-specific key routing for editor input."""
from __future__ import annotations

from collections.abc import Callable

from editor_commands_insert import handle_key as handle_insert_key
from editor_commands_normal import handle_key as handle_normal_key
from editor_state import EditorState


class ModeRouter:
    def __init__(
        self,
        state: EditorState,
        on_mode_change: Callable[[str], None],
        on_inline_delete: Callable[[str], bool],
    ) -> None:
        self._state = state
        self._on_mode_change = on_mode_change
        self._on_inline_delete = on_inline_delete

    def handle_key(self, key_name: str) -> bool:
        if self._state.mode == "normal":
            return handle_normal_key(key_name, self._on_mode_change)
        if self._state.mode == "insert":
            return handle_insert_key(key_name, self._on_mode_change, self._on_inline_delete)
        return False
