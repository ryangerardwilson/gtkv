"""UI status controller for mode/file/status hints."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from editor_state import EditorState

from ui_window_shell import WindowShell


class StatusController:
    def __init__(self, shell: WindowShell) -> None:
        self._shell = shell
        self._state: Optional[EditorState] = None

    def bind_state(self, state: EditorState) -> None:
        self._state = state
        state.add_listener(self._on_state_change)
        self._on_state_change(state)

    def update_status(self, mode: str, file_path: Optional[Path]) -> None:
        file_label = file_path.as_posix() if file_path else "[No File]"
        self._shell.set_status_text(f"{mode.upper()}  {file_label}")

    def set_status_text(self, message: str) -> None:
        self._shell.set_status_text(message)

    def set_hint(self, message: str) -> None:
        self._shell.set_status_hint(message)

    def refresh(self) -> None:
        if self._state:
            self._on_state_change(self._state)

    def _on_state_change(self, state: EditorState) -> None:
        self.update_status(state.mode, state.file_path)
