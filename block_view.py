from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from typing import Sequence
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
try:
    gi.require_version("WebKit", "6.0")
except ValueError:
    try:
        gi.require_version("WebKit", "4.1")
    except ValueError:
        pass
from gi.repository import Gdk, GLib, Gtk  # type: ignore[import-not-found, attr-defined]

try:
    from gi.repository import WebKit  # type: ignore[import-not-found, attr-defined]
except Exception:
    WebKit = None

import document_io
import keymap
from block_model import (
    BlockDocument,
    LatexBlock,
    MapBlock,
    PythonImageBlock,
    TextBlock,
    ThreeBlock,
    build_heading_numbering,
    sample_document,
)
from design_constants import colors_for
from latex_template import render_latex_html
from map_template import render_map_html
from three_template import render_three_html


@dataclass
class OutlineEntry:
    block_index: int
    kind: str
    depth: int
    text: str
    has_children: bool


@dataclass
class VaultEntry:
    path: Path
    label: str
    kind: str


@dataclass
class VaultAction:
    handled: bool
    opened_path: Path | None = None
    selected_vault_root: Path | None = None
    close: bool = False
    toggle_theme: bool = False
    locked: bool = False
    deploy: bool = False
    quit: bool = False


class _TocBlockView(Gtk.Frame):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.add_css_class("block")
        self.add_css_class("block-text")
        self.add_css_class("block-text-toc")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_hexpand(True)
        box.set_halign(Gtk.Align.FILL)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        title = Gtk.Label(label="Index")
        title.add_css_class("toc-index-label")
        title.set_halign(Gtk.Align.START)
        box.append(title)

        self._text_view = Gtk.TextView()
        self._text_view.set_monospace(True)
        self._text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._text_view.set_pixels_above_lines(0)
        self._text_view.set_pixels_below_lines(0)
        self._text_view.set_pixels_inside_wrap(0)
        self._text_view.set_editable(False)
        self._text_view.set_cursor_visible(False)
        self._text_view.set_left_margin(0)
        self._text_view.set_right_margin(0)

        buffer = self._text_view.get_buffer()
        buffer.set_text(text)
        box.append(self._text_view)

        self.set_child(box)

    def set_text(self, text: str) -> None:
        buffer = self._text_view.get_buffer()
        buffer.set_text(text)


class BlockEditorView(Gtk.Box):
    def __init__(
        self,
        ui_mode: str = "dark",
        keymap_config: keymap.Keymap | None = None,
        demo: bool = False,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self._ui_mode = ui_mode
        self._keymap = keymap_config
        self._demo = demo

        self._scroller = Gtk.ScrolledWindow()
        self._scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._scroller.set_hexpand(True)
        self._scroller.set_vexpand(True)
        self._scroller.set_can_focus(True)
        self._scroller.set_propagate_natural_height(False)
        self._scroller.set_propagate_natural_width(False)

        self._block_widgets: list[Gtk.Widget] = []
        self._selected_index = 0
        self._visual_active = False
        self._visual_anchor = 0
        self._visual_end = 0

        self._column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._column.set_margin_top(24)
        self._column.set_margin_bottom(160)
        self._column.set_margin_start(120)
        self._column.set_margin_end(120)
        self._column_padding: int | None = None
        self._scroller.add_tick_callback(self._tick_column_padding)
        self._column.set_valign(Gtk.Align.START)
        self._column.set_hexpand(True)

        self._help_visible = False
        self._help_scroller: Gtk.ScrolledWindow | None = None
        self._help_panel = self._build_help_overlay()
        self._help_scroll = 0.0
        self._help_selected = 0
        self._help_scroll_step = 42.0

        self._help_panel.set_visible(False)

        self._toc_visible = False
        self._toc_panel = self._build_toc_overlay()
        self._toc_panel.set_visible(False)
        self._toc_entries: list[OutlineEntry] = []
        self._toc_visible_entries: list[int] = []
        self._toc_rows: list[Gtk.Widget] = []
        self._toc_selected_entry = 0
        self._toc_expanded: set[int] = set()
        self._toc_scroll_before = 0.0
        self._toc_selected_before = 0

        self._vault_visible = False
        self._vault_panel = self._build_vault_overlay()
        self._vault_panel.set_visible(False)
        self._vault_entries: list[VaultEntry] = []
        self._vault_rows: list[Gtk.Widget] = []
        self._vault_selected = 0
        self._vault_screen = "chooser"
        self._vault_root: Path | None = None
        self._vault_path: Path | None = None
        self._vault_vaults: list[Path] = []
        self._vault_create_active = False
        self._vault_rename_active = False
        self._vault_rename_source: Path | None = None
        self._vault_clipboard_mode: str | None = None
        self._vault_clipboard_path: Path | None = None
        self._vault_clipboard_name: str | None = None
        self._vault_locked = False

        self._status_timer_id: int | None = None
        self._scroll_idle_id: int | None = None
        self._scroll_retries = 0
        self._scroller.set_child(self._column)

        self._overlay = Gtk.Overlay()
        self._overlay.set_hexpand(True)
        self._overlay.set_vexpand(True)
        self._overlay.set_child(self._scroller)
        self._overlay.add_overlay(self._toc_panel)
        self._overlay.add_overlay(self._help_panel)
        self._overlay.add_overlay(self._vault_panel)

        self._status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._status_bar.add_css_class("status-bar")
        self._status_bar.set_hexpand(True)
        self._status_bar.set_halign(Gtk.Align.CENTER)
        self._status_bar.set_valign(Gtk.Align.END)
        self._status_bar.set_margin_bottom(16)
        self._status_bar.set_visible(False)
        self._status_label = Gtk.Label()
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.set_hexpand(True)
        self._status_bar.append(self._status_label)
        self._overlay.add_overlay(self._status_bar)

        self.append(self._overlay)

        self._document: BlockDocument | None = None

    def set_document(self, document: BlockDocument) -> None:
        self._document = document
        for child in list(self._column):
            self._column.remove(child)

        self._block_widgets = []

        numbering = build_heading_numbering(document.blocks)
        toc_text = _build_toc(
            [block for block in document.blocks if isinstance(block, TextBlock)]
        )
        for index, block in enumerate(document.blocks):
            widget = self._build_widget(block, toc_text, self._ui_mode, numbering, index)
            if widget is None:
                continue
            self._block_widgets.append(widget)
            self._column.append(widget)

        self._selected_index = min(
            self._selected_index, max(len(self._block_widgets) - 1, 0)
        )
        self._refresh_selection()
        self._column.queue_resize()
        GLib.idle_add(self._column.queue_resize)

    def _tick_column_padding(self, _widget: Gtk.Widget, _frame_clock) -> bool:
        width = self._scroller.get_allocated_width()
        if width <= 0:
            return True
        padding = min(200, max(24, int((width - 600) * 0.4)))
        if padding == self._column_padding:
            return True
        self._column_padding = padding
        self._column.set_margin_start(padding)
        self._column.set_margin_end(padding)
        return True

    def insert_widget_after(self, index: int, block, document: BlockDocument) -> None:
        numbering = build_heading_numbering(document.blocks)
        toc_text = _build_toc(
            [item for item in document.blocks if isinstance(item, TextBlock)]
        )
        insert_index = min(index + 1, len(document.blocks) - 1)
        widget = self._build_widget(
            block, toc_text, self._ui_mode, numbering, insert_index
        )
        if widget is None:
            return
        insert_at = min(index + 1, len(self._block_widgets))
        self._block_widgets.insert(insert_at, widget)
        self._column.insert_child_after(
            widget, self._block_widgets[insert_at - 1] if insert_at > 0 else None
        )
        self.refresh_toc(document)
        self.refresh_heading_numbering(document)
        self._column.queue_resize()
        GLib.idle_add(self._column.queue_resize)

    def remove_widget_at(self, index: int, document: BlockDocument) -> None:
        if index < 0 or index >= len(self._block_widgets):
            return
        widget = self._block_widgets.pop(index)
        self._column.remove(widget)
        self.refresh_toc(document)
        self.refresh_heading_numbering(document)

    def refresh_heading_numbering(self, document: BlockDocument) -> None:
        numbering = build_heading_numbering(document.blocks)
        for index, (block, widget) in enumerate(zip(document.blocks, self._block_widgets)):
            if not isinstance(block, TextBlock):
                continue
            if block.kind not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                continue
            if not isinstance(widget, _TextBlockView):
                continue
            prefix = numbering.get(index, "")
            widget.set_text(_format_heading_label(prefix, block.text))

    def refresh_toc(self, document: BlockDocument) -> None:
        toc_text = _build_toc(
            [block for block in document.blocks if isinstance(block, TextBlock)]
        )
        for block, widget in zip(document.blocks, self._block_widgets):
            if isinstance(block, TextBlock) and block.kind == "toc":
                if isinstance(widget, _TocBlockView):
                    widget.set_text(toc_text)
        if not self._toc_visible:
            return
        selected_block_index = None
        selected_entry = self._get_selected_toc_entry()
        if selected_entry is not None:
            selected_block_index = selected_entry.block_index
        expanded_block_indices = set()
        for entry_index in self._toc_expanded:
            if 0 <= entry_index < len(self._toc_entries):
                expanded_block_indices.add(self._toc_entries[entry_index].block_index)
        self._toc_entries = self._build_outline_entries(document)
        self._toc_expanded = {
            index
            for index, entry in enumerate(self._toc_entries)
            if entry.has_children and entry.block_index in expanded_block_indices
        }
        if selected_block_index is not None:
            for index, entry in enumerate(self._toc_entries):
                if entry.block_index == selected_block_index:
                    self._toc_selected_entry = index
                    break
            else:
                self._toc_selected_entry = 0
        else:
            self._toc_selected_entry = 0
        self._render_toc_entries()
        self._schedule_toc_scroll()

    def move_selection(self, delta: int) -> None:
        if not self._block_widgets:
            return
        self._selected_index = max(
            0, min(self._selected_index + delta, len(self._block_widgets) - 1)
        )
        self._refresh_selection()
        self._schedule_scroll_to_selected()

    def visual_active(self) -> bool:
        return self._visual_active

    def toggle_visual_mode(self) -> None:
        if not self._block_widgets:
            return
        if self._visual_active:
            self.exit_visual_mode()
            return
        self._visual_active = True
        self._visual_anchor = self._selected_index
        self._visual_end = self._selected_index
        self._refresh_selection()

    def exit_visual_mode(self) -> None:
        if not self._visual_active:
            return
        self._visual_active = False
        self._refresh_selection()

    def get_visual_range(self) -> tuple[int, int]:
        start = min(self._visual_anchor, self._visual_end)
        end = max(self._visual_anchor, self._visual_end)
        return start, end

    def visual_move(self, delta: int) -> None:
        if not self._visual_active:
            return
        self._visual_end = max(
            0, min(self._visual_end + delta, len(self._block_widgets) - 1)
        )
        self._selected_index = self._visual_end
        self._refresh_selection()
        self._schedule_scroll_to_selected()

    def select_first(self) -> None:
        if not self._block_widgets:
            return
        self._selected_index = 0
        self._refresh_selection()
        self._schedule_scroll_to_selected()

    def select_last(self) -> None:
        if not self._block_widgets:
            return
        self._selected_index = len(self._block_widgets) - 1
        self._refresh_selection()
        self._schedule_scroll_to_selected()

    def focus_selected_block(self) -> bool:
        if not self._block_widgets:
            return False
        widget = self._block_widgets[self._selected_index]
        return isinstance(widget, _TextBlockView)

    def selected_block_is_text(self) -> bool:
        if not self._block_widgets:
            return False
        return isinstance(self._block_widgets[self._selected_index], _TextBlockView)

    def get_selected_index(self) -> int:
        return self._selected_index

    def get_scroll_position(self) -> float:
        vadjustment = self._scroller.get_vadjustment()
        if vadjustment is None:
            return 0.0
        return vadjustment.get_value()

    def set_scroll_position(self, value: float) -> None:
        vadjustment = self._scroller.get_vadjustment()
        if vadjustment is None:
            return
        vadjustment.set_value(max(0.0, value))

    def reload_media_at(self, index: int) -> bool:
        if not self._block_widgets:
            return False
        if index < 0 or index >= len(self._block_widgets):
            return False
        widget = self._block_widgets[index]
        if isinstance(widget, _PyImageBlockView):
            document = self._document
            if document is None:
                return False
            block = document.blocks[index]
            if isinstance(block, PythonImageBlock):
                widget.set_pending(False, block)
                widget.update_block(block, self._ui_mode)
                return True
        if isinstance(widget, _LatexBlockView):
            document = self._document
            if document is None:
                return False
            block = document.blocks[index]
            if isinstance(block, LatexBlock):
                widget.update_latex(block.source, self._ui_mode)
                return True
        if hasattr(widget, "reload_html"):
            try:
                widget.reload_html()
                return True
            except Exception:
                return False
        return False

    def update_text_at(self, index: int, text: str) -> bool:
        if not self._block_widgets:
            return False
        if index < 0 or index >= len(self._block_widgets):
            return False
        widget = self._block_widgets[index]
        if isinstance(widget, _TextBlockView):
            block = self._document.blocks[index] if self._document else None
            if isinstance(block, TextBlock) and block.kind in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                numbering = build_heading_numbering(self._document.blocks) if self._document else {}
                prefix = numbering.get(index, "")
                widget.set_text(_format_heading_label(prefix, text))
            else:
                widget.set_text(text)
            return True
        return False

    def set_pyimage_pending(self, index: int) -> bool:
        if not self._block_widgets:
            return False
        if index < 0 or index >= len(self._block_widgets):
            return False
        widget = self._block_widgets[index]
        if not isinstance(widget, _PyImageBlockView):
            return False
        document = self._document
        if document is None:
            return False
        block = document.blocks[index]
        if not isinstance(block, PythonImageBlock):
            return False
        widget.set_pending(True, block)
        pending = PythonImageBlock(
            block.source,
            format=block.format,
            rendered_data_dark=None,
            rendered_hash_dark=None,
            rendered_path_dark=None,
            rendered_data_light=None,
            rendered_hash_light=None,
            rendered_path_light=None,
            last_error=None,
        )
        widget.update_block(pending, self._ui_mode)
        return True

    def set_selected_index(self, index: int, scroll: bool = True) -> None:
        if not self._block_widgets:
            return
        self._selected_index = max(0, min(index, len(self._block_widgets) - 1))
        self._refresh_selection()
        if scroll:
            self._schedule_scroll_to_selected()

    def center_on_index(self, index: int) -> None:
        if not self._block_widgets:
            return
        if index < 0 or index >= len(self._block_widgets):
            return
        widget = self._block_widgets[index]
        allocation = widget.get_allocation()
        vadjustment = self._scroller.get_vadjustment()
        if vadjustment is None:
            return
        page = vadjustment.get_page_size()
        target = allocation.y + allocation.height / 2 - page / 2
        vadjustment.set_value(max(0.0, target))

    def move_widget(self, from_index: int, to_index: int) -> None:
        if not self._block_widgets:
            return
        if from_index < 0 or to_index < 0:
            return
        if from_index >= len(self._block_widgets) or to_index >= len(
            self._block_widgets
        ):
            return
        if from_index == to_index:
            return
        widget = self._block_widgets.pop(from_index)
        self._block_widgets.insert(to_index, widget)
        self._column.remove(widget)
        self._column.insert_child_after(
            widget, self._block_widgets[to_index - 1] if to_index > 0 else None
        )
        if hasattr(widget, "reload_html"):
            try:
                widget.reload_html()
            except Exception:
                pass

    def clear_selection(self) -> None:
        for widget in self._block_widgets:
            widget.remove_css_class("block-selected")

    def toggle_help(self) -> None:
        self._help_visible = not self._help_visible
        if self._help_visible:
            self.clear_selection()
            self._help_panel.set_visible(True)
            self._help_panel.grab_focus()
        else:
            self._help_panel.set_visible(False)

    def show_status(self, message: str, kind: str = "info") -> None:
        self._status_label.set_text(message)
        self._status_bar.remove_css_class("status-success")
        self._status_bar.remove_css_class("status-error")
        if kind == "success":
            self._status_bar.add_css_class("status-success")
        elif kind == "error":
            self._status_bar.add_css_class("status-error")
        self._status_bar.set_visible(True)
        if self._status_timer_id is not None:
            GLib.source_remove(self._status_timer_id)
        self._status_timer_id = GLib.timeout_add(2500, self._clear_status)

    def _clear_status(self) -> bool:
        self._status_bar.set_visible(False)
        self._status_timer_id = None
        return False

    def _restore_help_state(self) -> bool:
        self.set_selected_index(self._help_selected, scroll=False)
        self.set_scroll_position(self._help_scroll)
        return False

    def toc_drill_active(self) -> bool:
        return self._toc_visible

    def set_ui_mode(self, ui_mode: str, document: BlockDocument) -> None:
        if ui_mode == self._ui_mode:
            return
        scroll = self.get_scroll_position()
        selected = self._selected_index
        self._ui_mode = ui_mode
        self.set_document(document)
        self.set_selected_index(selected, scroll=False)
        self.set_scroll_position(scroll)
        GLib.idle_add(self._restore_scroll_position, scroll)
        GLib.timeout_add(120, self._restore_scroll_position, scroll)

    def _restore_scroll_position(self, scroll: float) -> bool:
        self.set_scroll_position(scroll)
        if self._block_widgets and self._selected_index == len(self._block_widgets) - 1:
            vadjustment = self._scroller.get_vadjustment()
            if vadjustment is not None:
                bottom = vadjustment.get_upper() - vadjustment.get_page_size()
                vadjustment.set_value(max(vadjustment.get_value(), bottom))
        return False

    def open_toc_drill(self, document: BlockDocument) -> None:
        if self._toc_visible:
            return
        self._toc_visible = True
        self._toc_scroll_before = self.get_scroll_position()
        self._toc_selected_before = self._selected_index
        self._toc_expanded = set()
        self._toc_entries = self._build_outline_entries(document)
        self._toc_selected_entry = 0
        if self._toc_entries:
            for i, entry in enumerate(self._toc_entries):
                if entry.block_index == self._selected_index:
                    self._toc_selected_entry = i
                    break
            else:
                for i, entry in enumerate(self._toc_entries):
                    if entry.block_index > self._selected_index:
                        self._toc_selected_entry = max(0, i - 1)
                        break
        self._render_toc_entries()
        self._toc_panel.set_visible(True)
        self._toc_panel.grab_focus()
        self._schedule_toc_scroll()

    def close_toc_drill(self, restore: bool = True) -> None:
        if not self._toc_visible:
            return
        self._toc_visible = False
        self._toc_panel.set_visible(False)
        if restore:
            self.set_selected_index(self._toc_selected_before, scroll=False)
            self.set_scroll_position(self._toc_scroll_before)

    def handle_toc_drill_key(self, keyval: int, state: int) -> bool:
        if not self._toc_visible:
            return False
        if self._keymap is None:
            return False
        token = keymap.event_to_token(keyval, state)
        if token is None:
            return False
        action, handled = self._keymap.match("toc", token)
        if not handled:
            return False
        if action is None:
            return True
        if action == "help_toggle":
            self.toggle_help()
            return True
        if action == "close":
            self.close_toc_drill(restore=True)
            return True
        if action == "open":
            entry = self._get_selected_toc_entry()
            if entry is None:
                self.close_toc_drill(restore=True)
                return True
            block_index = entry.block_index
            self.set_selected_index(block_index)
            self.center_on_index(block_index)
            self.close_toc_drill(restore=False)
            return True
        if action == "move_down":
            self._move_toc_selection(1)
            return True
        if action == "move_up":
            self._move_toc_selection(-1)
            return True
        if action == "collapse_or_parent":
            self._collapse_or_parent()
            return True
        if action == "expand_or_child":
            self._expand_or_child()
            return True
        if action == "expand_all":
            self._expand_all_toc()
            return True
        if action == "toggle_selected":
            self._toggle_selected_toc()
            return True
        if action == "collapse_all":
            self._collapse_all_toc()
            return True
        return True

    def handle_help_key(self, keyval: int, state: int) -> bool:
        if not self._help_visible:
            return False
        if self._keymap is None:
            return False
        token = keymap.event_to_token(keyval, state)
        if token is None:
            return False
        action, handled = self._keymap.match("help", token)
        if not handled:
            return False
        if action is None:
            return True
        if action == "close":
            self.toggle_help()
            return True
        if action == "scroll_down":
            self._scroll_help(self._help_scroll_step)
            return True
        if action == "scroll_up":
            self._scroll_help(-self._help_scroll_step)
            return True
        return True

    def _scroll_help(self, delta: float) -> None:
        if self._help_scroller is None:
            return
        vadjustment = self._help_scroller.get_vadjustment()
        if vadjustment is None:
            return
        current = vadjustment.get_value()
        lower = vadjustment.get_lower()
        upper = vadjustment.get_upper() - vadjustment.get_page_size()
        vadjustment.set_value(max(lower, min(upper, current + delta)))

    def vault_active(self) -> bool:
        return self._vault_visible

    def open_vault_mode(self, vaults: Sequence[Path], locked: bool = False) -> None:
        self._vault_visible = True
        self._vault_panel.set_visible(True)
        self._vault_locked = locked
        self._vault_vaults = list(vaults)
        if self._vault_locked and self._vault_vaults:
            self._vault_screen = "browser"
            self._vault_root = self._vault_vaults[0]
            self._vault_path = self._vault_root
        elif len(self._vault_vaults) == 1:
            self._vault_screen = "browser"
            self._vault_root = self._vault_vaults[0]
            self._vault_path = self._vault_root
        else:
            self._vault_screen = "chooser"
            self._vault_root = None
            self._vault_path = None
        self._vault_selected = 0
        self._render_vault_entries()
        self._vault_panel.grab_focus()

    def close_vault_mode(self) -> None:
        if not self._vault_visible:
            return
        self._vault_visible = False
        self._vault_panel.set_visible(False)
        self._clear_vault_clipboard()

    def handle_vault_key(self, keyval: int, state: int) -> VaultAction:
        if not self._vault_visible:
            return VaultAction(False)
        if self._vault_create_active:
            if keyval == Gdk.KEY_Escape:
                self._cancel_vault_create()
                return VaultAction(True)
            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                if self._confirm_vault_create():
                    return VaultAction(True)
                return VaultAction(True)
            return VaultAction(False)
        if self._vault_rename_active:
            if keyval == Gdk.KEY_Escape:
                self._cancel_vault_rename()
                return VaultAction(True)
            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                if self._confirm_vault_rename():
                    return VaultAction(True)
                return VaultAction(True)
            return VaultAction(False)
        if self._keymap is None:
            return VaultAction(False)
        token = keymap.event_to_token(keyval, state)
        if token is None:
            return VaultAction(False)
        action, handled = self._keymap.match("vault", token)
        if not handled:
            return VaultAction(False)
        if action is None:
            return VaultAction(True)
        if action == "close":
            return VaultAction(True, close=True)
        if action == "quit":
            return VaultAction(True, quit=True)
        if action == "move_down":
            self._move_vault_selection(1)
            return VaultAction(True)
        if action == "move_up":
            self._move_vault_selection(-1)
            return VaultAction(True)
        if action == "up":
            if (
                self._vault_screen == "browser"
                and self._vault_root is not None
                and self._vault_path is not None
                and self._vault_path != self._vault_root
            ):
                self._vault_path = self._vault_path.parent
                self._vault_selected = 0
                self._render_vault_entries()
            if self._vault_path == self._vault_root and self._vault_locked:
                return VaultAction(True, locked=True)
            return VaultAction(True)
        if action == "enter_or_open":
            entry = self._get_selected_vault_entry()
            if entry is None:
                return VaultAction(True)
            if self._vault_screen == "chooser":
                self._vault_screen = "browser"
                self._vault_root = entry.path
                self._vault_path = entry.path
                self._vault_locked = True
                self._vault_selected = 0
                self._render_vault_entries()
                return VaultAction(True, selected_vault_root=entry.path)
            if entry.kind == "dir":
                self._vault_path = entry.path
                self._vault_selected = 0
                self._render_vault_entries()
                return VaultAction(True)
            if entry.kind == "file":
                return VaultAction(True, opened_path=entry.path)
            return VaultAction(True)
        if action == "deploy_sync":
            return VaultAction(True, deploy=True)
        if action == "copy":
            self._vault_copy_selected()
            return VaultAction(True)
        if action == "cut":
            self._vault_cut_selected()
            return VaultAction(True)
        if action == "paste":
            self._vault_paste_clipboard()
            return VaultAction(True)
        if action == "new_entry":
            self._start_vault_create()
            return VaultAction(True)
        if action == "rename":
            self._start_vault_rename()
            return VaultAction(True)
        if action == "toggle_theme":
            return VaultAction(True, toggle_theme=True)
        return VaultAction(True)

    def _build_vault_overlay(self) -> Gtk.Widget:
        overlay = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        overlay.set_hexpand(True)
        overlay.set_vexpand(True)
        overlay.set_halign(Gtk.Align.CENTER)
        overlay.set_valign(Gtk.Align.START)
        overlay.set_margin_top(32)
        overlay.add_css_class("vault-overlay")

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        panel.add_css_class("vault-panel")
        panel.set_halign(Gtk.Align.CENTER)
        panel.set_valign(Gtk.Align.START)
        panel.set_margin_top(12)
        panel.set_margin_bottom(12)
        panel.set_margin_start(12)
        panel.set_margin_end(12)

        title = Gtk.Label(label="Vault")
        title.add_css_class("vault-title")
        title.set_halign(Gtk.Align.START)
        panel.append(title)

        subtitle = Gtk.Label(label="")
        subtitle.add_css_class("vault-subtitle")
        subtitle.set_halign(Gtk.Align.START)
        panel.append(subtitle)

        hint = Gtk.Label(label="")
        hint.add_css_class("vault-hint")
        hint.set_halign(Gtk.Align.START)
        hint.set_visible(False)
        panel.append(hint)

        create_entry = Gtk.Entry()
        create_entry.set_placeholder_text("New file or directory")
        create_entry.set_hexpand(True)
        create_entry.set_visible(False)
        create_entry.add_css_class("vault-entry")
        panel.append(create_entry)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_min_content_height(320)

        vault_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vault_list.add_css_class("vault-list")
        scroller.set_child(vault_list)
        panel.append(scroller)

        self._vault_title_label = title
        self._vault_subtitle_label = subtitle
        self._vault_hint_label = hint
        self._vault_create_entry = create_entry
        self._vault_list = vault_list
        self._vault_scroller = scroller

        overlay.append(panel)
        return overlay

    def _render_vault_entries(self) -> None:
        self._vault_create_entry.set_visible(False)
        self._vault_create_active = False
        if self._vault_rename_active:
            self._vault_rename_active = False
            self._vault_rename_source = None
        for child in list(self._vault_list):
            self._vault_list.remove(child)
        self._vault_rows = []

        entries: list[VaultEntry] = []
        empty_text = ""

        if self._vault_screen == "chooser":
            self._vault_title_label.set_text("Vaults")
            if self._vault_vaults:
                self._vault_subtitle_label.set_text("Select a vault")
            else:
                self._vault_subtitle_label.set_text("")
            for vault in self._vault_vaults:
                name = vault.name or str(vault)
                label = f"{name} - {vault}"
                entries.append(VaultEntry(path=vault, label=label, kind="vault"))
            if not entries:
                empty_text = "No vaults registered"
        else:
            self._vault_title_label.set_text("Vault")
            root = self._vault_root
            path = self._vault_path
            if root is None or path is None:
                self._vault_subtitle_label.set_text("")
                empty_text = "No .gvim files in this folder"
            else:
                if path == root:
                    self._vault_subtitle_label.set_text("/")
                else:
                    relative = path.relative_to(root).as_posix()
                    self._vault_subtitle_label.set_text(f"/{relative}")
                entries = self._collect_vault_entries(path)
                if not entries:
                    empty_text = "No .gvim files in this folder"

        self._vault_entries = entries

        if not entries:
            empty = Gtk.Label(label=empty_text)
            empty.add_css_class("vault-empty")
            empty.set_halign(Gtk.Align.START)
            self._vault_list.append(empty)
            return

        if self._vault_selected >= len(entries):
            self._vault_selected = max(0, len(entries) - 1)

        for index, entry in enumerate(entries):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            row.add_css_class("vault-row")
            if index == self._vault_selected:
                row.add_css_class("vault-row-selected")
            label = Gtk.Label(label=entry.label)
            label.add_css_class("vault-row-label")
            label.set_halign(Gtk.Align.START)
            label.set_hexpand(True)
            row.append(label)
            self._vault_list.append(row)
            self._vault_rows.append(row)

        GLib.idle_add(self._scroll_vault_to_selected)

    def _start_vault_create(self) -> None:
        if self._vault_screen != "browser":
            self.show_status("Select a vault first", "error")
            return
        self._vault_create_active = True
        self._vault_create_entry.set_text("")
        self._vault_create_entry.set_visible(True)
        self._vault_create_entry.grab_focus()

    def _cancel_vault_create(self) -> None:
        self._vault_create_active = False
        self._vault_create_entry.set_visible(False)
        self._vault_panel.grab_focus()

    def _start_vault_rename(self) -> None:
        if self._vault_screen != "browser":
            self.show_status("Select a vault first", "error")
            return
        entry = self._get_selected_vault_entry()
        if entry is None or entry.kind not in {"dir", "file"}:
            self.show_status("Nothing to rename", "error")
            return
        self._vault_rename_active = True
        self._vault_rename_source = entry.path
        self._vault_create_entry.set_text(entry.label.rstrip("/"))
        self._vault_create_entry.select_region(-1, -1)
        self._vault_create_entry.set_position(-1)
        self._vault_create_entry.set_visible(True)
        self._vault_create_entry.grab_focus()
        GLib.idle_add(self._clear_vault_entry_selection)

    def _cancel_vault_rename(self) -> None:
        self._vault_rename_active = False
        self._vault_rename_source = None
        self._vault_create_entry.set_visible(False)
        self._vault_panel.grab_focus()

    def _clear_vault_entry_selection(self) -> bool:
        self._vault_create_entry.select_region(-1, -1)
        self._vault_create_entry.set_position(-1)
        return False

    def _confirm_vault_create(self) -> bool:
        text = self._vault_create_entry.get_text().strip()
        if not text:
            self.show_status("Name required", "error")
            return False
        if self._vault_root is None or self._vault_path is None:
            self.show_status("No vault open", "error")
            return False
        if Path(text).is_absolute():
            self.show_status("Name must be relative", "error")
            return False
        target = (self._vault_path / text).resolve()
        root = self._vault_root.resolve()
        if not self._vault_path_in_root(target, root):
            self.show_status("Path must stay in vault", "error")
            return False
        target = self._vault_unique_path(target)
        if target.suffix == ".gvim":
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                if self._demo:
                    document_io.save(target, sample_document())
                else:
                    document_io.save(
                        target, BlockDocument([TextBlock("Untitled", kind="title")])
                    )
            except OSError:
                self.show_status("Failed to create file", "error")
                return False
        else:
            try:
                target.mkdir(parents=True, exist_ok=True)
            except OSError:
                self.show_status("Failed to create directory", "error")
                return False
        self._vault_create_active = False
        self._vault_create_entry.set_visible(False)
        self._vault_selected = 0
        self._render_vault_entries()
        self._vault_panel.grab_focus()
        return True

    def _confirm_vault_rename(self) -> bool:
        text = self._vault_create_entry.get_text().strip()
        if not text:
            self.show_status("Name required", "error")
            return False
        if self._vault_root is None or self._vault_path is None:
            self.show_status("No vault open", "error")
            return False
        if self._vault_rename_source is None:
            self.show_status("Nothing to rename", "error")
            return False
        if Path(text).is_absolute():
            self.show_status("Name must be relative", "error")
            return False
        target = (self._vault_path / text).resolve()
        root = self._vault_root.resolve()
        if not self._vault_path_in_root(target, root):
            self.show_status("Path must stay in vault", "error")
            return False
        if target.exists():
            self.show_status("Already exists", "error")
            return False
        try:
            shutil.move(self._vault_rename_source.as_posix(), target.as_posix())
        except OSError:
            self.show_status("Rename failed", "error")
            return False
        self._vault_rename_active = False
        self._vault_rename_source = None
        self._vault_create_entry.set_visible(False)
        self._vault_selected = 0
        self._render_vault_entries()
        self._vault_panel.grab_focus()
        self.show_status("Renamed", "success")
        return True

    def _vault_path_in_root(self, target: Path, root: Path) -> bool:
        if target == root:
            return True
        return root in target.parents

    def _clear_vault_clipboard(self) -> None:
        if self._vault_clipboard_mode != "cut" or self._vault_clipboard_path is None:
            self._vault_clipboard_mode = None
            self._vault_clipboard_path = None
            self._vault_clipboard_name = None
            return
        try:
            if self._vault_clipboard_path.exists():
                if self._vault_clipboard_path.is_dir():
                    shutil.rmtree(self._vault_clipboard_path)
                else:
                    self._vault_clipboard_path.unlink()
        except OSError:
            pass
        self._vault_clipboard_mode = None
        self._vault_clipboard_path = None
        self._vault_clipboard_name = None

    def _vault_cut_storage_dir(self, root: Path) -> Path:
        return root / ".gvim_cut"

    def _vault_unique_path(self, target: Path) -> Path:
        if not target.exists():
            return target
        suffix = target.suffix
        stem = target.stem if suffix else target.name
        parent = target.parent
        index = 1
        while True:
            name = f"{stem}_{index}{suffix}"
            candidate = parent / name
            if not candidate.exists():
                return candidate
            index += 1

    def _vault_cut_selected(self) -> None:
        entry = self._get_selected_vault_entry()
        if entry is None:
            self.show_status("Nothing to cut", "error")
            return
        if entry.kind not in {"dir", "file"}:
            self.show_status("Nothing to cut", "error")
            return
        if self._vault_root is None:
            self.show_status("No vault open", "error")
            return
        cut_name = entry.label.rstrip("/")
        storage_dir = self._vault_cut_storage_dir(self._vault_root)
        target = self._vault_unique_path(storage_dir / cut_name)
        try:
            storage_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(entry.path.as_posix(), target.as_posix())
        except OSError:
            self.show_status("Cut failed", "error")
            return
        self._vault_clipboard_mode = "cut"
        self._vault_clipboard_path = target
        self._vault_clipboard_name = cut_name
        self.show_status(f"Cut: {cut_name}", "success")
        self._vault_selected = 0
        self._render_vault_entries()

    def _vault_copy_selected(self) -> None:
        entry = self._get_selected_vault_entry()
        if entry is None:
            self.show_status("Nothing to copy", "error")
            return
        if entry.kind not in {"dir", "file"}:
            self.show_status("Nothing to copy", "error")
            return
        self._vault_clipboard_mode = "copy"
        self._vault_clipboard_path = entry.path
        self._vault_clipboard_name = entry.label.rstrip("/")
        self.show_status(f"Copied: {self._vault_clipboard_name}", "success")

    def _vault_paste_clipboard(self) -> None:
        if not self._vault_clipboard_mode or self._vault_clipboard_path is None:
            self.show_status("Nothing to paste", "error")
            return
        if self._vault_root is None or self._vault_path is None:
            self.show_status("No vault open", "error")
            return
        source = self._vault_clipboard_path
        if self._vault_clipboard_mode == "cut" and self._vault_clipboard_name:
            destination_base = self._vault_path / self._vault_clipboard_name
        else:
            destination_base = self._vault_path / source.name
        destination = self._vault_unique_path(destination_base)
        root = self._vault_root.resolve()
        if not self._vault_path_in_root(destination.resolve(), root):
            self.show_status("Path must stay in vault", "error")
            return
        if not source.exists():
            self.show_status("Clipboard missing", "error")
            self._vault_clipboard_mode = None
            self._vault_clipboard_path = None
            self._vault_clipboard_name = None
            return
        if source.is_dir() and self._vault_path_in_root(
            destination.resolve(), source.resolve()
        ):
            self.show_status("Cannot paste into itself", "error")
            return
        try:
            if self._vault_clipboard_mode == "cut":
                shutil.move(source.as_posix(), destination.as_posix())
                self._vault_clipboard_mode = None
                self._vault_clipboard_path = None
                self._vault_clipboard_name = None
            else:
                if source.is_dir():
                    shutil.copytree(source.as_posix(), destination.as_posix())
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source.as_posix(), destination.as_posix())
            self.show_status("Pasted", "success")
        except OSError:
            self.show_status("Paste failed", "error")
            return
        self._vault_selected = 0
        self._render_vault_entries()

    def _collect_vault_entries(self, path: Path) -> list[VaultEntry]:
        try:
            children = list(path.iterdir())
        except OSError:
            return []
        cut_path = (
            self._vault_clipboard_path if self._vault_clipboard_mode == "cut" else None
        )
        dirs: list[VaultEntry] = []
        files: list[VaultEntry] = []
        for child in children:
            name = child.name
            if name in {".git", ".github"}:
                continue
            if cut_path is not None and child == cut_path:
                continue
            if child.is_dir():
                dirs.append(VaultEntry(path=child, label=f"{name}/", kind="dir"))
            elif child.is_file() and child.suffix == ".gvim":
                files.append(VaultEntry(path=child, label=name, kind="file"))
        dirs.sort(key=lambda entry: entry.label.lower())
        files.sort(key=lambda entry: entry.label.lower())
        return dirs + files

    def _move_vault_selection(self, delta: int) -> None:
        if not self._vault_entries:
            return
        new_index = max(
            0, min(self._vault_selected + delta, len(self._vault_entries) - 1)
        )
        if new_index == self._vault_selected:
            return
        if 0 <= self._vault_selected < len(self._vault_rows):
            self._vault_rows[self._vault_selected].remove_css_class(
                "vault-row-selected"
            )
        self._vault_selected = new_index
        if 0 <= self._vault_selected < len(self._vault_rows):
            self._vault_rows[self._vault_selected].add_css_class("vault-row-selected")
        self._scroll_vault_to_selected()

    def _get_selected_vault_entry(self) -> VaultEntry | None:
        if not self._vault_entries:
            return None
        if self._vault_selected < 0 or self._vault_selected >= len(self._vault_entries):
            return None
        return self._vault_entries[self._vault_selected]

    def _scroll_vault_to_selected(self) -> bool:
        if not self._vault_rows or self._vault_scroller is None:
            return False
        if self._vault_selected < 0 or self._vault_selected >= len(self._vault_rows):
            return False
        row = self._vault_rows[self._vault_selected]
        allocation = row.get_allocation()
        vadjustment = self._vault_scroller.get_vadjustment()
        if vadjustment is None:
            return False
        top = allocation.y
        bottom = allocation.y + allocation.height
        view_top = vadjustment.get_value()
        view_bottom = view_top + vadjustment.get_page_size()
        if top < view_top:
            vadjustment.set_value(max(0, top - 12))
        elif bottom > view_bottom:
            vadjustment.set_value(max(0, bottom - vadjustment.get_page_size() + 12))
        return False

    def _build_toc_overlay(self) -> Gtk.Widget:
        overlay = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        overlay.set_hexpand(True)
        overlay.set_vexpand(True)
        overlay.set_halign(Gtk.Align.CENTER)
        overlay.set_valign(Gtk.Align.START)
        overlay.set_margin_top(32)
        overlay.add_css_class("toc-overlay")

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        panel.add_css_class("toc-panel")
        panel.set_halign(Gtk.Align.CENTER)
        panel.set_valign(Gtk.Align.START)
        panel.set_margin_top(12)
        panel.set_margin_bottom(12)
        panel.set_margin_start(12)
        panel.set_margin_end(12)

        title = Gtk.Label(label="Index")
        title.add_css_class("toc-title")
        title.set_halign(Gtk.Align.START)
        panel.append(title)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_min_content_height(320)

        toc_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        toc_list.add_css_class("toc-list")
        scroller.set_child(toc_list)
        panel.append(scroller)

        self._toc_list = toc_list
        self._toc_scroller = scroller

        overlay.append(panel)
        return overlay

    def _build_outline_entries(self, document: BlockDocument) -> list[OutlineEntry]:
        entries: list[OutlineEntry] = []
        depth_map = {"h1": 0, "h2": 1, "h3": 2, "h4": 3, "h5": 4, "h6": 5}
        numbering = build_heading_numbering(document.blocks)
        for index, block in enumerate(document.blocks):
            if isinstance(block, TextBlock) and block.kind in {
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
            }:
                text = block.text.strip().splitlines()[0] if block.text.strip() else ""
                prefix = numbering.get(index, "")
                label = _format_heading_label(prefix, text)
                entries.append(
                    OutlineEntry(
                        block_index=index,
                        kind=block.kind,
                        depth=depth_map[block.kind],
                        text=label,
                        has_children=False,
                    )
                )
        for i in range(len(entries) - 1):
            if entries[i + 1].depth > entries[i].depth:
                entries[i].has_children = True
        return entries

    def _render_toc_entries(self) -> None:
        for child in list(self._toc_list):
            self._toc_list.remove(child)
        self._toc_rows = []
        self._toc_visible_entries = []

        if not self._toc_entries:
            empty = Gtk.Label(label="No headings yet")
            empty.add_css_class("toc-empty")
            empty.set_halign(Gtk.Align.START)
            self._toc_list.append(empty)
            return

        visible_set: set[int] = set()
        for i, entry in enumerate(self._toc_entries):
            if entry.depth == 0:
                self._toc_visible_entries.append(i)
                visible_set.add(i)
                continue
            parent_index = self._find_parent_entry_index(i)
            if parent_index is None:
                continue
            if parent_index in visible_set and parent_index in self._toc_expanded:
                self._toc_visible_entries.append(i)
                visible_set.add(i)

        if self._toc_selected_entry not in self._toc_visible_entries:
            self._toc_selected_entry = self._toc_visible_entries[0]

        for visible_index, entry_index in enumerate(self._toc_visible_entries):
            entry = self._toc_entries[entry_index]
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            row.add_css_class("toc-row")
            if entry_index == self._toc_selected_entry:
                row.add_css_class("toc-row-selected")

            marker = ">" if entry.has_children else " "
            label = Gtk.Label(label=f"{marker} {entry.text}")
            label.add_css_class("toc-row-label")
            label.set_halign(Gtk.Align.START)
            row.set_margin_start(12 + entry.depth * 16)
            row.append(label)
            self._toc_list.append(row)
            self._toc_rows.append(row)

    def _get_selected_toc_entry(self) -> OutlineEntry | None:
        if not self._toc_entries or not self._toc_visible_entries:
            return None
        return self._toc_entries[self._toc_selected_entry]

    def _move_toc_selection(self, delta: int) -> None:
        if not self._toc_visible_entries:
            return
        current = self._toc_visible_entries.index(self._toc_selected_entry)
        next_index = max(0, min(current + delta, len(self._toc_visible_entries) - 1))
        self._toc_selected_entry = self._toc_visible_entries[next_index]
        self._render_toc_entries()
        self._schedule_toc_scroll()

    def _collapse_or_parent(self) -> None:
        entry = self._get_selected_toc_entry()
        if entry is None:
            return
        if entry.has_children and self._toc_selected_entry in self._toc_expanded:
            self._toc_expanded.remove(self._toc_selected_entry)
            self._render_toc_entries()
            self._schedule_toc_scroll()
            return
        parent_index = self._find_parent_entry_index(self._toc_selected_entry)
        if parent_index is not None:
            self._toc_selected_entry = parent_index
            self._render_toc_entries()
            self._schedule_toc_scroll()

    def _expand_or_child(self) -> None:
        entry = self._get_selected_toc_entry()
        if entry is None:
            return
        if entry.has_children and self._toc_selected_entry not in self._toc_expanded:
            self._toc_expanded.add(self._toc_selected_entry)
            self._render_toc_entries()
            self._schedule_toc_scroll()
            return
        child_index = self._find_first_child_entry_index(self._toc_selected_entry)
        if child_index is not None:
            self._toc_selected_entry = child_index
            self._render_toc_entries()
            self._schedule_toc_scroll()

    def _expand_all_toc(self) -> None:
        self._toc_expanded = {
            index for index, entry in enumerate(self._toc_entries) if entry.has_children
        }
        self._render_toc_entries()
        self._schedule_toc_scroll()

    def _collapse_all_toc(self) -> None:
        self._toc_expanded = set()
        self._render_toc_entries()
        self._schedule_toc_scroll()

    def _toggle_selected_toc(self) -> None:
        entry = self._get_selected_toc_entry()
        if entry is None or not entry.has_children:
            return
        if self._toc_selected_entry in self._toc_expanded:
            self._toc_expanded.remove(self._toc_selected_entry)
        else:
            self._toc_expanded.add(self._toc_selected_entry)
        self._render_toc_entries()
        self._schedule_toc_scroll()

    def _find_parent_entry_index(self, entry_index: int) -> int | None:
        if entry_index <= 0:
            return None
        depth = self._toc_entries[entry_index].depth
        for i in range(entry_index - 1, -1, -1):
            if self._toc_entries[i].depth < depth:
                return i
        return None

    def _find_first_child_entry_index(self, entry_index: int) -> int | None:
        if entry_index < 0 or entry_index >= len(self._toc_entries) - 1:
            return None
        depth = self._toc_entries[entry_index].depth
        next_entry = self._toc_entries[entry_index + 1]
        if next_entry.depth > depth:
            return entry_index + 1
        return None

    def _schedule_toc_scroll(self) -> None:
        GLib.idle_add(self._scroll_toc_to_selected)

    def _scroll_toc_to_selected(self) -> bool:
        if not self._toc_visible_entries or not self._toc_rows:
            return False
        display_index = self._toc_visible_entries.index(self._toc_selected_entry)
        row = self._toc_rows[display_index]
        allocation = row.get_allocation()
        vadjustment = self._toc_scroller.get_vadjustment()
        if vadjustment is None:
            return False
        top = allocation.y
        bottom = allocation.y + allocation.height
        view_top = vadjustment.get_value()
        view_bottom = view_top + vadjustment.get_page_size()
        if top < view_top:
            vadjustment.set_value(max(0, top - 8))
        elif bottom > view_bottom:
            vadjustment.set_value(max(0, bottom - vadjustment.get_page_size() + 8))
        return False

    def refresh_selection(self) -> None:
        self._refresh_selection()

    def _refresh_selection(self) -> None:
        start = None
        end = None
        multi_range = False
        if self._visual_active:
            start, end = self.get_visual_range()
            multi_range = start != end
        for index, widget in enumerate(self._block_widgets):
            in_range = False
            if start is not None and end is not None:
                in_range = start <= index <= end
            widget.remove_css_class("block-range-start")
            widget.remove_css_class("block-range-middle")
            widget.remove_css_class("block-range-end")
            if index == self._selected_index:
                widget.add_css_class("block-selected")
                widget.remove_css_class("block-selected-range")
            elif in_range:
                widget.remove_css_class("block-selected")
                widget.add_css_class("block-selected-range")
            else:
                widget.remove_css_class("block-selected")
                widget.remove_css_class("block-selected-range")
            if not in_range or not multi_range:
                continue
            if index == start:
                widget.add_css_class("block-range-start")
            elif index == end:
                widget.add_css_class("block-range-end")
            else:
                widget.add_css_class("block-range-middle")

    def _schedule_scroll_to_selected(self) -> None:
        if self._scroll_idle_id is not None:
            return
        self._scroll_retries = 0
        self._scroll_idle_id = GLib.idle_add(self._deferred_scroll_to_selected)

    def _deferred_scroll_to_selected(self) -> bool:
        if self._scroll_to_selected_if_needed():
            self._scroll_idle_id = None
            return False
        self._scroll_retries += 1
        if self._scroll_retries >= 3:
            self._scroll_idle_id = None
            return False
        return True

    def _scroll_to_selected_if_needed(self) -> bool:
        if not self._block_widgets:
            return True
        widget = self._block_widgets[self._selected_index]
        allocation = widget.get_allocation()
        vadjustment = self._scroller.get_vadjustment()
        if vadjustment is None:
            return True
        if allocation.height <= 0 and allocation.y == 0:
            return False
        top = allocation.y
        bottom = allocation.y + allocation.height
        if self._selected_index == len(self._block_widgets) - 1:
            bottom += 120
        view_top = vadjustment.get_value()
        view_bottom = view_top + vadjustment.get_page_size()
        if view_top <= top and bottom <= view_bottom:
            return True
        if top < view_top:
            vadjustment.set_value(max(0, top - 12))
        elif bottom > view_bottom:
            vadjustment.set_value(max(0, bottom - vadjustment.get_page_size() + 12))
        return True

    def _build_help_overlay(self) -> Gtk.Widget:
        overlay = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        overlay.set_hexpand(True)
        overlay.set_vexpand(True)
        overlay.set_halign(Gtk.Align.CENTER)
        overlay.set_valign(Gtk.Align.START)
        overlay.set_margin_top(40)
        overlay.add_css_class("help-overlay")

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        panel.add_css_class("help-panel")
        panel.set_halign(Gtk.Align.CENTER)
        panel.set_valign(Gtk.Align.START)
        panel.set_margin_top(12)
        panel.set_margin_bottom(12)
        panel.set_margin_start(12)
        panel.set_margin_end(12)

        title = Gtk.Label(label="Shortcuts")
        title.add_css_class("help-title")
        title.set_halign(Gtk.Align.START)
        panel.append(title)

        if self._keymap is None:
            lines = []
        else:
            lines = keymap.build_help_lines(self._keymap)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_min_content_height(280)

        body = Gtk.Label(label="\n".join(lines))
        body.add_css_class("help-body")
        body.set_halign(Gtk.Align.START)
        body.set_selectable(False)
        scroller.set_child(body)
        panel.append(scroller)

        self._help_scroller = scroller

        overlay.append(panel)
        return overlay

    @staticmethod
    def _build_widget(
        block,
        toc_text: str,
        ui_mode: str,
        numbering: dict[int, str],
        index: int,
    ) -> Gtk.Widget | None:
        if isinstance(block, TextBlock):
            if block.kind == "toc":
                return _TocBlockView(toc_text)
            if block.kind in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                prefix = numbering.get(index, "")
                return _TextBlockView(_format_heading_label(prefix, block.text), block.kind)
            return _TextBlockView(block.text, block.kind)
        if isinstance(block, ThreeBlock):
            return _ThreeBlockView(block.source, ui_mode)
        if isinstance(block, PythonImageBlock):
            return _PyImageBlockView(block, ui_mode)
        if isinstance(block, LatexBlock):
            return _LatexBlockView(block.source, ui_mode)
        if isinstance(block, MapBlock):
            return _MapBlockView(block.source, ui_mode)
        return None


class _TextBlockView(Gtk.Frame):
    def __init__(self, text: str, kind: str) -> None:
        super().__init__()
        self.add_css_class("block")
        self.add_css_class("block-text")
        self.add_css_class(f"block-text-{kind}")

        self._text_view = Gtk.TextView()
        self._text_view.set_monospace(True)
        self._text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        if kind in {"title", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._text_view.set_top_margin(10)
            self._text_view.set_bottom_margin(8)
        else:
            self._text_view.set_top_margin(12)
            self._text_view.set_bottom_margin(12)
        self._text_view.set_left_margin(12)
        self._text_view.set_right_margin(12)
        if kind in {"title", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._text_view.set_pixels_above_lines(1)
            self._text_view.set_pixels_below_lines(1)
        else:
            self._text_view.set_pixels_above_lines(0)
            self._text_view.set_pixels_below_lines(0)
        self._text_view.set_pixels_inside_wrap(0)
        self._text_view.set_editable(False)
        self._text_view.set_cursor_visible(False)

        buffer = self._text_view.get_buffer()
        buffer.set_text(text)

        self.set_child(self._text_view)

    def set_text(self, text: str) -> None:
        buffer = self._text_view.get_buffer()
        buffer.set_text(text)


class _ThreeBlockView(Gtk.Frame):
    def __init__(self, source: str, ui_mode: str) -> None:
        super().__init__()
        self._ui_mode = ui_mode
        self.add_css_class("block")
        self.add_css_class("block-three")

        self.view = None
        self._html = None
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        _apply_block_padding(self._box)
        if WebKit is None:
            label = Gtk.Label(label="WebKitGTK not available for 3D blocks")
            _apply_block_padding(label)
            self.set_child(label)
            return

        if not source.strip():
            label = Gtk.Label(label="Empty 3D block")
            _apply_block_padding(label)
            self.set_child(label)
            return

        source = render_three_html(source, ui_mode).replace(
            "__GVIM_THREE_SRC__", _three_module_uri()
        )
        self._html = source
        self._build_view()
        self.set_child(self._box)

    def reload_html(self) -> None:
        if self.view is None or self._html is None:
            return
        self.view.load_html(self._html, "file:///")

    def _build_view(self) -> None:
        if WebKit is None:
            return
        palette = colors_for(self._ui_mode)
        bg_red, bg_green, bg_blue, bg_alpha = palette.webkit_background_rgba
        view = WebKit.WebView()  # type: ignore[union-attr, attr-defined]
        settings = view.get_settings()
        if settings is not None:
            if hasattr(settings, "set_enable_javascript"):
                settings.set_enable_javascript(True)
            if hasattr(settings, "set_enable_webgl"):
                settings.set_enable_webgl(True)
            if hasattr(settings, "set_enable_developer_extras"):
                settings.set_enable_developer_extras(True)
            if hasattr(settings, "set_allow_file_access_from_file_urls"):
                settings.set_allow_file_access_from_file_urls(True)
            if hasattr(settings, "set_allow_universal_access_from_file_urls"):
                settings.set_allow_universal_access_from_file_urls(True)
        background = Gdk.RGBA()
        background.red = bg_red
        background.green = bg_green
        background.blue = bg_blue
        background.alpha = bg_alpha
        if hasattr(view, "set_background_color"):
            view.set_background_color(background)
        view.set_vexpand(False)
        view.set_hexpand(True)
        view.set_size_request(-1, 300)
        view.load_html(self._html, "file:///")
        self.view = view
        self._box.append(view)


class _PyImageBlockView(Gtk.Frame):
    def __init__(self, block: PythonImageBlock, ui_mode: str) -> None:
        super().__init__()
        self._ui_mode = ui_mode
        self._pending = False
        self.add_css_class("block")
        self.add_css_class("block-image")
        self.add_css_class("block-pyimage")
        self.set_hexpand(True)
        self.set_halign(Gtk.Align.FILL)
        self.update_block(block, ui_mode)

    def update_block(self, block: PythonImageBlock, ui_mode: str) -> None:
        if self._pending:
            self._set_pending_label(block)
            return
        if ui_mode == "light":
            rendered_data = block.rendered_data_light
            rendered_hash = block.rendered_hash_light
            rendered_path = block.rendered_path_light
        else:
            rendered_data = block.rendered_data_dark
            rendered_hash = block.rendered_hash_dark
            rendered_path = block.rendered_path_dark

        path = rendered_path or _materialize_pyimage(rendered_data, rendered_hash)
        if path and os.path.exists(path):
            picture = Gtk.Picture.new_for_filename(path)
            picture.set_can_shrink(True)
            picture.set_content_fit(Gtk.ContentFit.SCALE_DOWN)
            picture.set_size_request(-1, 300)
            picture.set_vexpand(False)
            picture.set_hexpand(True)
            picture.set_halign(Gtk.Align.FILL)
            picture.set_valign(Gtk.Align.START)
            picture.add_css_class("pyimage-picture")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.set_hexpand(True)
            box.set_halign(Gtk.Align.FILL)
            _apply_block_padding(box)
            box.add_css_class("pyimage-container")
            box.append(picture)
            self.set_child(box)
            return

        self._set_pending_label(block)

    def set_pending(self, pending: bool, block: PythonImageBlock) -> None:
        self._pending = pending
        if pending:
            self._set_pending_label(block)
        else:
            self.update_block(block, self._ui_mode)

    def _set_pending_label(self, block: PythonImageBlock) -> None:
        label_text = "Rendering"
        if block.last_error:
            label_text = "Python render error (see editor)"
        label = Gtk.Label(label=label_text)
        _apply_block_padding(label)
        self.set_child(label)


class _LatexBlockView(Gtk.Frame):
    def __init__(self, source: str, ui_mode: str) -> None:
        super().__init__()
        self._ui_mode = ui_mode
        self.add_css_class("block")
        self.add_css_class("block-three")

        self.view = None
        self._html = None
        self._pending_load = False
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        _apply_block_padding(self._box)

        if WebKit is None:
            label = Gtk.Label(label="WebKitGTK not available for LaTeX blocks")
            _apply_block_padding(label)
            self.set_child(label)
            return

        if not source.strip():
            label = Gtk.Label(label="Empty LaTeX block")
            _apply_block_padding(label)
            self.set_child(label)
            return

        view = WebKit.WebView()  # type: ignore[union-attr]
        settings = view.get_settings()
        if settings is not None:
            if hasattr(settings, "set_enable_javascript"):
                settings.set_enable_javascript(True)
            if hasattr(settings, "set_allow_file_access_from_file_urls"):
                settings.set_allow_file_access_from_file_urls(True)
            if hasattr(settings, "set_allow_universal_access_from_file_urls"):
                settings.set_allow_universal_access_from_file_urls(True)
        palette = colors_for(self._ui_mode)
        bg_red, bg_green, bg_blue, bg_alpha = palette.webkit_background_rgba
        background = Gdk.RGBA()
        background.red = bg_red
        background.green = bg_green
        background.blue = bg_blue
        background.alpha = bg_alpha
        if hasattr(view, "set_background_color"):
            view.set_background_color(background)
        view.set_vexpand(False)
        view.set_hexpand(True)
        view.set_size_request(-1, 80)
        view.set_valign(Gtk.Align.START)
        self._html = render_latex_html(source, ui_mode)
        self._pending_load = True
        if hasattr(view, "get_mapped") and view.get_mapped():
            view.load_html(self._html, "file:///")
            self._pending_load = False
        else:
            view.connect("map", self._on_map_load_html)
        if hasattr(view, "connect") and hasattr(view, "run_javascript"):
            view.connect("load-changed", self._on_latex_load_changed)
        self.view = view
        self._box.append(view)
        self.set_child(self._box)

    def reload_html(self) -> None:
        if self.view is None or self._html is None:
            return
        if hasattr(self.view, "get_mapped") and not self.view.get_mapped():
            self._pending_load = True
            return
        self.view.load_html(self._html, "file:///")

    def update_latex(self, source: str, ui_mode: str) -> None:
        self._ui_mode = ui_mode
        if self.view is None:
            return
        self._html = render_latex_html(source, ui_mode)
        if hasattr(self.view, "get_mapped") and not self.view.get_mapped():
            self._pending_load = True
            return
        self.view.load_html(self._html, "file:///")

    def _on_map_load_html(self, view: Gtk.Widget) -> None:
        if not self._pending_load:
            return
        if self._html is None:
            return
        if hasattr(view, "load_html"):
            view.load_html(self._html, "file:///")
        self._pending_load = False


class _MapBlockView(Gtk.Frame):
    def __init__(self, source: str, ui_mode: str) -> None:
        super().__init__()
        self._ui_mode = ui_mode
        self.add_css_class("block")
        self.add_css_class("block-map")

        self.view_dark = None
        self.view_light = None
        self._html_dark = None
        self._html_light = None
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        _apply_block_padding(self._box)

        if WebKit is None:
            label = Gtk.Label(label="WebKitGTK not available for map blocks")
            _apply_block_padding(label)
            self.set_child(label)
            return

        if not source.strip():
            label = Gtk.Label(label="Empty map block")
            _apply_block_padding(label)
            self.set_child(label)
            return

        self._html_dark = render_map_html(source, "dark")
        self._html_light = render_map_html(source, "light")

        self.view_dark = self._build_map_view(self._html_dark)
        self.view_light = self._build_map_view(self._html_light)

        self._box.append(self.view_dark)
        self._box.append(self.view_light)
        self._set_theme_visibility()
        self.set_child(self._box)

    def reload_html(self) -> None:
        if self.view_dark is not None and self._html_dark is not None:
            self.view_dark.load_html(  # type: ignore[union-attr]
                self._html_dark, "file:///"
            )
        if self.view_light is not None and self._html_light is not None:
            self.view_light.load_html(  # type: ignore[union-attr]
                self._html_light, "file:///"
            )

    def _build_map_view(self, html: str) -> Gtk.Widget:
        view = WebKit.WebView()  # type: ignore[union-attr]
        settings = view.get_settings()
        if settings is not None:
            if hasattr(settings, "set_enable_javascript"):
                settings.set_enable_javascript(True)
            if hasattr(settings, "set_allow_universal_access_from_file_urls"):
                settings.set_allow_universal_access_from_file_urls(True)
        palette = colors_for(self._ui_mode)
        bg_red, bg_green, bg_blue, bg_alpha = palette.webkit_background_rgba
        background = Gdk.RGBA()
        background.red = bg_red
        background.green = bg_green
        background.blue = bg_blue
        background.alpha = bg_alpha
        if hasattr(view, "set_background_color"):
            view.set_background_color(background)
        view.set_vexpand(False)
        view.set_hexpand(True)
        view.set_size_request(-1, 320)
        view.load_html(html, "file:///")
        return view

    def _set_theme_visibility(self) -> None:
        if self.view_dark is None or self.view_light is None:
            return
        is_dark = self._ui_mode == "dark"
        self.view_dark.set_visible(is_dark)
        self.view_light.set_visible(not is_dark)

    def _on_latex_load_changed(self, view, load_event) -> None:
        if WebKit is None:
            return
        if load_event != WebKit.LoadEvent.FINISHED:
            return
        if not hasattr(view, "run_javascript"):
            return

        def _on_js_finished(_view, result) -> None:
            if WebKit is None:
                return
            try:
                value = _view.run_javascript_finish(result)
            except Exception:
                return
            try:
                height = value.to_int64() if value is not None else 0
            except Exception:
                height = 0
            if height and height > 0:
                view.set_size_request(-1, int(height) + 8)

        view.run_javascript(
            "Math.ceil(document.body.scrollHeight)",
            None,
            _on_js_finished,
        )


def _three_module_uri() -> str:
    bundled = Path(__file__).with_name("three.module.min.js")
    return bundled.resolve().as_uri()


def _build_toc(blocks: Sequence[TextBlock]) -> str:
    headings = []
    numbering = build_heading_numbering(blocks)
    for index, block in enumerate(blocks):
        if isinstance(block, TextBlock) and block.kind in {
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        }:
            text = block.text.strip().splitlines()[0] if block.text.strip() else ""
            prefix = numbering.get(index, "")
            headings.append((block.kind, _format_heading_label(prefix, text)))

    if not headings:
        return "(No headings yet)"

    lines = []
    for kind, text in headings:
        indent = ""
        if kind == "h2":
            indent = "  "
        elif kind == "h3":
            indent = "    "
        elif kind == "h4":
            indent = "      "
        elif kind == "h5":
            indent = "        "
        elif kind == "h6":
            indent = "          "
        lines.append(f"{indent}- {text}")
    return "\n".join(lines)


def _format_heading_label(prefix: str, text: str) -> str:
    prefix = prefix.strip()
    text = text.strip()
    if not prefix:
        return text
    if not text:
        return prefix
    return f"{prefix} {text}"


def _apply_block_padding(widget: Gtk.Widget, padding: int = 12) -> None:
    widget.set_margin_top(padding)
    widget.set_margin_bottom(padding)
    widget.set_margin_start(padding)
    widget.set_margin_end(padding)


def _materialize_pyimage(
    rendered_data: str | None, rendered_hash: str | None
) -> str | None:
    if not rendered_data:
        return None
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache_dir = cache_root / "gvim" / "pyimage"
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest_source = rendered_hash or rendered_data
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:16]
    extension = ".svg"
    image_path = cache_dir / f"pyimage-{digest}{extension}"
    try:
        image_path.write_text(rendered_data, encoding="utf-8")
    except (OSError, ValueError):
        return None
    return image_path.as_posix()
