from __future__ import annotations

import hashlib
import os
import time
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

from block_model import (
    BlockDocument,
    LatexBlock,
    MapBlock,
    PythonImageBlock,
    TextBlock,
    ThreeBlock,
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
    def __init__(self, ui_mode: str = "dark") -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self._ui_mode = ui_mode

        self._scroller = Gtk.ScrolledWindow()
        self._scroller.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )
        self._scroller.set_hexpand(True)
        self._scroller.set_vexpand(True)
        self._scroller.set_can_focus(True)
        self._scroller.set_propagate_natural_height(False)
        self._scroller.set_propagate_natural_width(False)

        self._block_widgets: list[Gtk.Widget] = []
        self._selected_index = 0

        self._column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._column.set_margin_top(24)
        self._column.set_margin_bottom(160)
        self._column.set_margin_start(24)
        self._column.set_margin_end(24)
        self._column.set_valign(Gtk.Align.START)

        self._help_visible = False
        self._help_panel = self._build_help_overlay()
        self._help_scroll = 0.0
        self._help_selected = 0

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
        self._toc_leader_active = False
        self._toc_leader_buffer = ""
        self._toc_leader_start = 0.0

        self._status_timer_id: int | None = None
        self._scroll_idle_id: int | None = None
        self._scroll_retries = 0
        self._status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._status_bar.add_css_class("status-bar")
        self._status_bar.set_hexpand(True)
        self._status_bar.set_visible(False)
        self._status_label = Gtk.Label()
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.set_hexpand(True)
        self._status_bar.append(self._status_label)

        self._scroller.set_child(self._column)

        self._overlay = Gtk.Overlay()
        self._overlay.set_hexpand(True)
        self._overlay.set_vexpand(True)
        self._overlay.set_child(self._scroller)
        self._overlay.add_overlay(self._toc_panel)
        self._overlay.add_overlay(self._help_panel)

        self.append(self._overlay)
        self.append(self._status_bar)

    def set_document(self, document: BlockDocument) -> None:
        for child in list(self._column):
            self._column.remove(child)

        self._block_widgets = []

        toc_text = _build_toc(
            [block for block in document.blocks if isinstance(block, TextBlock)]
        )
        for block in document.blocks:
            widget = self._build_widget(block, toc_text, self._ui_mode)
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

    def insert_widget_after(self, index: int, block, document: BlockDocument) -> None:
        toc_text = _build_toc(
            [item for item in document.blocks if isinstance(item, TextBlock)]
        )
        widget = self._build_widget(block, toc_text, self._ui_mode)
        if widget is None:
            return
        insert_at = min(index + 1, len(self._block_widgets))
        self._block_widgets.insert(insert_at, widget)
        self._column.insert_child_after(
            widget, self._block_widgets[insert_at - 1] if insert_at > 0 else None
        )
        self.refresh_toc(document)

    def remove_widget_at(self, index: int, document: BlockDocument) -> None:
        if index < 0 or index >= len(self._block_widgets):
            return
        widget = self._block_widgets.pop(index)
        self._column.remove(widget)
        self.refresh_toc(document)

    def refresh_toc(self, document: BlockDocument) -> None:
        toc_text = _build_toc(
            [block for block in document.blocks if isinstance(block, TextBlock)]
        )
        for block, widget in zip(document.blocks, self._block_widgets):
            if isinstance(block, TextBlock) and block.kind == "toc":
                if isinstance(widget, _TocBlockView):
                    widget.set_text(toc_text)

    def move_selection(self, delta: int) -> None:
        if not self._block_widgets:
            return
        self._selected_index = max(
            0, min(self._selected_index + delta, len(self._block_widgets) - 1)
        )
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
        if hasattr(widget, "reload_html"):
            try:
                widget.reload_html()
                return True
            except Exception:
                return False
        return False

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

    def handle_toc_drill_key(self, keyval: int) -> bool:
        if not self._toc_visible:
            return False
        if self._toc_leader_active and time.monotonic() - self._toc_leader_start > 2.0:
            self._toc_leader_active = False
            self._toc_leader_buffer = ""
        if keyval == ord(",") and not self._toc_leader_active:
            self._toc_leader_active = True
            self._toc_leader_buffer = ""
            self._toc_leader_start = time.monotonic()
            return True
        if self._toc_leader_active:
            if keyval == Gdk.KEY_Escape:
                self._toc_leader_active = False
                self._toc_leader_buffer = ""
                return True
            if 32 <= keyval <= 126:
                self._toc_leader_buffer += chr(keyval)
            else:
                return True
            if self._toc_leader_buffer == "xar":
                self._toc_leader_active = False
                self._toc_leader_buffer = ""
                self._expand_all_toc()
                return True
            if self._toc_leader_buffer == "xr":
                self._toc_leader_active = False
                self._toc_leader_buffer = ""
                self._toggle_selected_toc()
                return True
            if self._toc_leader_buffer == "xc":
                self._toc_leader_active = False
                self._toc_leader_buffer = ""
                self._collapse_all_toc()
                return True
            if not any(
                command.startswith(self._toc_leader_buffer)
                for command in ("xar", "xr", "xc")
            ):
                self._toc_leader_active = False
                self._toc_leader_buffer = ""
            return True
        if keyval in (ord("?"), Gdk.KEY_question):
            self.toggle_help()
            return True
        if keyval in (Gdk.KEY_Escape, ord("q"), ord("Q")):
            self.close_toc_drill(restore=True)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            entry = self._get_selected_toc_entry()
            if entry is None:
                self.close_toc_drill(restore=True)
                return True
            block_index = entry.block_index
            self.set_selected_index(block_index)
            self.center_on_index(block_index)
            self.close_toc_drill(restore=False)
            return True
        if keyval in (ord("j"), ord("J")):
            self._move_toc_selection(1)
            return True
        if keyval in (ord("k"), ord("K")):
            self._move_toc_selection(-1)
            return True
        if keyval in (ord("h"), ord("H")):
            self._collapse_or_parent()
            return True
        if keyval in (ord("l"), ord("L")):
            self._expand_or_child()
            return True
        return True

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

        title = Gtk.Label(label="Table of Contents")
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
        depth_map = {"h1": 0, "h2": 1, "h3": 2}
        for index, block in enumerate(document.blocks):
            if isinstance(block, TextBlock) and block.kind in {"h1", "h2", "h3"}:
                text = block.text.strip().splitlines()[0] if block.text.strip() else ""
                if not text:
                    continue
                entries.append(
                    OutlineEntry(
                        block_index=index,
                        kind=block.kind,
                        depth=depth_map[block.kind],
                        text=text,
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
            index
            for index, entry in enumerate(self._toc_entries)
            if entry.has_children
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
        for index, widget in enumerate(self._block_widgets):
            if index == self._selected_index:
                widget.add_css_class("block-selected")
            else:
                widget.remove_css_class("block-selected")

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

    @staticmethod
    def _build_help_overlay() -> Gtk.Widget:
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

        lines = [
            "Navigation",
            "  j/k        move selection",
            "  Ctrl+j/k   move block",
            "  ,j         last block",
            "  ,k         first block",
            "  ,toc       outline drill",
            "  ,m         toggle theme",
            "  dd         cut selected block",
            "  yy         yank selected block",
            "  p          paste clipboard block",
            "  g/G        first/last block",
            "  Enter      edit selected block",
            "  q          quit without saving",
            "",
            "Blocks",
            "  ,bn        normal text",
            "  ,bht       title",
            "  ,bh1 ,bh2 ,bh3 headings",
            "  ,btoc      table of contents",
            "  ,bjs       Three.js block",
            "  ,bpy       Python render",
            "  ,bltx      LaTeX block",
            "  ,bmap      map block",
            "",
            "Other",
            "  Ctrl+S     save",
            "  Ctrl+E     export html",
            "  Ctrl+T     save and exit",
            "  Ctrl+X     exit without saving",
            "  ?          toggle this help",
        ]
        body = Gtk.Label(label="\n".join(lines))
        body.add_css_class("help-body")
        body.set_halign(Gtk.Align.START)
        panel.append(body)

        overlay.append(panel)
        return overlay

    @staticmethod
    def _build_widget(block, toc_text: str, ui_mode: str) -> Gtk.Widget | None:
        if isinstance(block, TextBlock):
            if block.kind == "toc":
                return _TocBlockView(toc_text)
            return _TextBlockView(block.text, block.kind)
        if isinstance(block, ThreeBlock):
            return _ThreeBlockView(block.source, ui_mode)
        if isinstance(block, PythonImageBlock):
            return _PyImageBlockView(block)
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
        if kind in {"title", "h1", "h2", "h3"}:
            self._text_view.set_top_margin(18)
            self._text_view.set_bottom_margin(14)
        else:
            self._text_view.set_top_margin(12)
            self._text_view.set_bottom_margin(12)
        self._text_view.set_left_margin(12)
        self._text_view.set_right_margin(12)
        if kind in {"title", "h1", "h2", "h3"}:
            self._text_view.set_pixels_above_lines(4)
            self._text_view.set_pixels_below_lines(4)
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
            "__GTKV_THREE_SRC__", _three_module_uri()
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
        view = WebKit.WebView()  # type: ignore[union-attr]
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
    def __init__(self, block: PythonImageBlock) -> None:
        super().__init__()
        self.add_css_class("block")
        self.add_css_class("block-image")
        self.add_css_class("block-pyimage")
        self.set_hexpand(True)
        self.set_halign(Gtk.Align.FILL)

        path = block.rendered_path or _materialize_pyimage(block)
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

        label_text = "Python render pending"
        if block.last_error:
            label_text = f"Python render error: {block.last_error}"
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

        view = WebKit.WebView()
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
        view.load_html(self._html, "file:///")
        if hasattr(view, "connect") and hasattr(view, "run_javascript"):
            view.connect("load-changed", self._on_latex_load_changed)
        self.view = view
        self._box.append(view)
        self.set_child(self._box)

    def reload_html(self) -> None:
        if self.view is None or self._html is None:
            return
        self.view.load_html(self._html, "file:///")


class _MapBlockView(Gtk.Frame):
    def __init__(self, source: str, ui_mode: str) -> None:
        super().__init__()
        self._ui_mode = ui_mode
        self.add_css_class("block")
        self.add_css_class("block-map")

        self.view = None
        self._html = None
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

        view = WebKit.WebView()
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
        self._html = render_map_html(source, ui_mode)
        view.load_html(self._html, "file:///")
        self.view = view
        self._box.append(view)
        self.set_child(self._box)

    def reload_html(self) -> None:
        if self.view is None or self._html is None:
            return
        self.view.load_html(self._html, "file:///")

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
    for block in blocks:
        if isinstance(block, TextBlock) and block.kind in {"h1", "h2", "h3"}:
            text = block.text.strip().splitlines()[0] if block.text.strip() else ""
            if text:
                headings.append((block.kind, text))

    if not headings:
        return "(No headings yet)"

    lines = []
    for kind, text in headings:
        indent = ""
        if kind == "h2":
            indent = "  "
        elif kind == "h3":
            indent = "    "
        lines.append(f"{indent}- {text}")
    return "\n".join(lines)


def _apply_block_padding(widget: Gtk.Widget, padding: int = 12) -> None:
    widget.set_margin_top(padding)
    widget.set_margin_bottom(padding)
    widget.set_margin_start(padding)
    widget.set_margin_end(padding)


def _materialize_pyimage(block: PythonImageBlock) -> str | None:
    if not block.rendered_data:
        return None
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache_dir = cache_root / "gtkv" / "pyimage"
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest_source = block.rendered_hash or block.rendered_data
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:16]
    extension = ".svg"
    image_path = cache_dir / f"pyimage-{digest}{extension}"
    try:
        image_path.write_text(block.rendered_data, encoding="utf-8")
    except (OSError, ValueError):
        return None
    return image_path.as_posix()
