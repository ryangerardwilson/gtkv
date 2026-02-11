"""Command pane for Vim-style input."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # type: ignore


class CommandPane:
    """Bottom command input and search pane."""

    def __init__(self) -> None:
        self._root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._root.set_margin_top(2)
        self._root.set_margin_bottom(2)
        self._root.set_margin_start(6)
        self._root.set_margin_end(6)

        self._prefix_label = Gtk.Label(label=":")
        self._prefix_label.set_xalign(0.0)

        self._entry = Gtk.Entry()
        self._entry.set_hexpand(True)
        self._entry.set_visibility(True)

        self._hint_label = Gtk.Label(label="")
        self._hint_label.set_xalign(1.0)

        self._root.append(self._prefix_label)
        self._root.append(self._entry)
        self._root.append(self._hint_label)

        self.set_visible(False)

    @property
    def widget(self) -> Gtk.Widget:
        return self._root

    def set_visible(self, visible: bool) -> None:
        self._root.set_visible(visible)

    def set_prefix(self, text: str) -> None:
        self._prefix_label.set_text(text)

    def set_hint(self, text: str) -> None:
        self._hint_label.set_text(text)

    def grab_focus(self) -> None:
        self._entry.grab_focus()

    def clear(self) -> None:
        self._entry.set_text("")

    def get_text(self) -> str:
        return self._entry.get_text()

    def connect_activate(self, handler) -> None:
        self._entry.connect("activate", handler)

    def connect_changed(self, handler) -> None:
        self._entry.connect("changed", handler)

    def add_key_controller(self, controller: Gtk.EventControllerKey) -> None:
        self._entry.add_controller(controller)
