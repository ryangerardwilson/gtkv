"""UI status controller for mode/file/status hints."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ui_window_shell import WindowShell


class StatusController:
    def __init__(self, shell: WindowShell) -> None:
        self._shell = shell

    def update_status(self, mode: str, file_path: Optional[Path]) -> None:
        file_label = file_path.as_posix() if file_path else "[No File]"
        self._shell.set_status_text(f"{mode.upper()}  {file_label}")

    def set_status_text(self, message: str) -> None:
        self._shell.set_status_text(message)

    def set_hint(self, message: str) -> None:
        self._shell.set_status_hint(message)
