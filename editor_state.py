"""Editor state for Vim-like mode handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from collections.abc import Callable


@dataclass
class EditorState:
    """Minimal editor state placeholder for Vim-like mode handling."""

    mode: str = "normal"
    file_path: Optional[Path] = None
    _listeners: list[Callable[["EditorState"], None]] = field(
        default_factory=list, init=False, repr=False
    )

    def add_listener(self, listener: Callable[["EditorState"], None]) -> None:
        self._listeners.append(listener)

    def set_mode(self, mode: str) -> None:
        if self.mode == mode:
            return
        self.mode = mode
        self._notify()

    def set_file_path(self, path: Optional[Path]) -> None:
        if self.file_path == path:
            return
        self.file_path = path
        self._notify()

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener(self)
