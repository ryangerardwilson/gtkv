"""GTK window shell layout and status bar."""
from __future__ import annotations

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # type: ignore

from ui_command_pane import CommandPane
from ui_editor_view import EditorView


class WindowShell:
    """Wraps window layout, status, and command pane."""

    def __init__(self, window: Gtk.ApplicationWindow) -> None:
        self._window = window
        self._root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._apply_transparent_theme()

        self._editor_view = EditorView(window)
        self._status_label = Gtk.Label(label="")
        self._status_label.set_xalign(0.0)

        self._command_pane = CommandPane()

        self._root.append(self._editor_view.widget)
        self._root.append(self._status_label)
        self._root.append(self._command_pane.widget)

        window.set_child(self._root)

    @property
    def editor_view(self) -> EditorView:
        return self._editor_view

    @property
    def command_pane(self) -> CommandPane:
        return self._command_pane

    def set_status_text(self, text: str) -> None:
        self._status_label.set_text(text)

    def set_status_hint(self, text: str) -> None:
        self._status_label.set_text(text)

    def _apply_transparent_theme(self) -> None:
        if hasattr(self._window, "set_app_paintable"):
            self._window.set_app_paintable(True)

        css = b"""
        window,
        .background,
        scrolledwindow,
        textview,
        textview text {
            background-color: transparent;
        }
        .inline-image {
            -gtk-icon-size: unset;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
