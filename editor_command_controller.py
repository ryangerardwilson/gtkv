"""Command pane controller for Vim-style commands."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # type: ignore

from ui_command_pane import CommandPane


class CommandController:
    def __init__(
        self,
        pane: CommandPane,
        on_ex_command: Callable[[str], bool],
        on_search: Callable[[str], bool],
        on_search_preview: Callable[[str], bool],
        on_status: Callable[[str], None],
        on_focus_editor: Callable[[], None],
    ) -> None:
        self._pane = pane
        self._on_ex_command = on_ex_command
        self._on_search = on_search
        self._on_search_preview = on_search_preview
        self._on_status = on_status
        self._on_focus_editor = on_focus_editor
        self._prefix: str | None = None
        self._history: list[str] = []
        self._history_index: int | None = None

    def bind(self) -> None:
        self._pane.connect_activate(self._on_command_activate)
        self._pane.connect_changed(self._on_command_changed)
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_command_key_pressed)
        self._pane.add_key_controller(controller)

    def show(self, prefix: str) -> None:
        self._prefix = prefix
        self._pane.set_prefix(prefix)
        self._pane.clear()
        self._pane.set_hint("")
        self._pane.set_visible(True)
        self._pane.grab_focus()
        self._history_index = None

    def hide(self) -> None:
        self._pane.set_visible(False)
        self._pane.clear()
        self._pane.set_hint("")
        self._on_focus_editor()
        self._prefix = None
        self._history_index = None

    def _on_command_activate(self, _entry) -> None:
        text = self._pane.get_text()
        prefix = self._prefix or ":"
        handled = False
        if prefix == ":":
            handled = self._on_ex_command(text)
        elif prefix == "/":
            handled = self._on_search(text)
        if not handled:
            self._on_status("UNKNOWN COMMAND")
        if text.strip():
            self._history.append(f"{prefix}{text}")
        self.hide()

    def _on_command_changed(self, _entry) -> None:
        if self._prefix != "/":
            return
        term = self._pane.get_text().strip()
        if not term:
            self._pane.set_hint("")
            return
        found = self._on_search_preview(term)
        if not found:
            self._pane.set_hint("NOT FOUND")
        else:
            self._pane.set_hint("")

    def _on_command_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        key_name = Gdk.keyval_name(keyval) or ""
        if key_name == "Escape":
            self.hide()
            return True
        if key_name == "Up":
            return self._history_move(-1)
        if key_name == "Down":
            return self._history_move(1)
        return False

    def _history_move(self, delta: int) -> bool:
        if not self._history:
            return False
        if self._history_index is None:
            self._history_index = len(self._history)
        self._history_index = max(
            0, min(len(self._history) - 1, self._history_index + delta)
        )
        entry = self._history[self._history_index]
        if entry.startswith(":") or entry.startswith("/"):
            self._pane.set_prefix(entry[0])
            self._prefix = entry[0]
            self._pane.set_text(entry[1:])
        else:
            self._pane.set_text(entry)
        return True
