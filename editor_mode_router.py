"""Mode-specific key routing for editor input."""

from __future__ import annotations

from collections.abc import Callable

from editor_commands_insert import handle_key as handle_insert_key
from editor_commands_normal import handle_key as handle_normal_key
from editor_commands_visual import handle_key as handle_visual_key
from editor_state import EditorState


class ModeRouter:
    def __init__(
        self,
        state: EditorState,
        on_mode_change: Callable[[str], None],
        on_inline_delete: Callable[[str], bool],
        on_move: Callable[[str, bool], bool],
        on_append: Callable[[str], None],
        on_open_line: Callable[[str], None],
    ) -> None:
        self._state = state
        self._on_mode_change = on_mode_change
        self._on_inline_delete = on_inline_delete
        self._on_move = on_move
        self._on_append = on_append
        self._on_open_line = on_open_line

    def handle_key(self, key_name: str) -> bool:
        if self._state.mode == "normal":
            return handle_normal_key(
                key_name,
                self._on_mode_change,
                self._on_move,
                self._on_append,
                self._on_open_line,
            )
        if self._state.mode == "insert":
            return handle_insert_key(
                key_name, self._on_mode_change, self._on_inline_delete, self._on_move
            )
        if self._state.mode == "visual":
            return handle_visual_key(key_name, self._on_mode_change, self._on_move)
        return False
