from __future__ import annotations

import os

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from block_model import BlockDocument, ImageBlock, TextBlock


class BlockEditorView(Gtk.ScrolledWindow):
    def __init__(self) -> None:
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.set_can_focus(True)

        self._block_widgets: list[Gtk.Widget] = []
        self._selected_index = 0

        self._column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self._column.set_margin_top(24)
        self._column.set_margin_bottom(24)
        self._column.set_margin_start(24)
        self._column.set_margin_end(24)

        self.set_child(self._column)

    def set_document(self, document: BlockDocument) -> None:
        for child in list(self._column):
            self._column.remove(child)

        self._block_widgets = []

        for block in document.blocks:
            if isinstance(block, TextBlock):
                widget = _TextBlockView(block.text)
            elif isinstance(block, ImageBlock):
                widget = _ImageBlockView(block.path, block.alt)
            else:
                continue
            self._block_widgets.append(widget)
            self._column.append(widget)

        self._selected_index = min(self._selected_index, max(len(self._block_widgets) - 1, 0))
        self._refresh_selection()

    def move_selection(self, delta: int) -> None:
        if not self._block_widgets:
            return
        self._selected_index = max(0, min(self._selected_index + delta, len(self._block_widgets) - 1))
        self._refresh_selection()

    def select_first(self) -> None:
        if not self._block_widgets:
            return
        self._selected_index = 0
        self._refresh_selection()

    def select_last(self) -> None:
        if not self._block_widgets:
            return
        self._selected_index = len(self._block_widgets) - 1
        self._refresh_selection()

    def focus_selected_block(self) -> bool:
        if not self._block_widgets:
            return False
        widget = self._block_widgets[self._selected_index]
        if isinstance(widget, _TextBlockView):
            widget.focus_editor()
            return True
        return False

    def selected_block_is_text(self) -> bool:
        if not self._block_widgets:
            return False
        return isinstance(self._block_widgets[self._selected_index], _TextBlockView)

    def clear_selection(self) -> None:
        for widget in self._block_widgets:
            widget.remove_css_class("block-selected")

    def refresh_selection(self) -> None:
        self._refresh_selection()

    def _refresh_selection(self) -> None:
        for index, widget in enumerate(self._block_widgets):
            if index == self._selected_index:
                widget.add_css_class("block-selected")
            else:
                widget.remove_css_class("block-selected")


class _TextBlockView(Gtk.Frame):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.add_css_class("block")
        self.add_css_class("block-text")

        self._text_view = Gtk.TextView()
        self._text_view.set_monospace(True)
        self._text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._text_view.set_top_margin(12)
        self._text_view.set_bottom_margin(12)
        self._text_view.set_left_margin(12)
        self._text_view.set_right_margin(12)
        self._text_view.set_vexpand(False)

        buffer = self._text_view.get_buffer()
        buffer.set_text(text)

        self.set_child(self._text_view)

    def focus_editor(self) -> None:
        self._text_view.grab_focus()


class _ImageBlockView(Gtk.Frame):
    def __init__(self, path: str, alt: str) -> None:
        super().__init__()
        self.add_css_class("block")
        self.add_css_class("block-image")

        if os.path.exists(path):
            picture = Gtk.Picture.new_for_filename(path)
            picture.set_can_shrink(True)
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            picture.set_margin_top(12)
            picture.set_margin_bottom(12)
            picture.set_margin_start(12)
            picture.set_margin_end(12)
            self.set_child(picture)
        else:
            label = Gtk.Label(label=f"Missing image: {alt or path}")
            label.set_margin_top(12)
            label.set_margin_bottom(12)
            label.set_margin_start(12)
            label.set_margin_end(12)
            self.set_child(label)
