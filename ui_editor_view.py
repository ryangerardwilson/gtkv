"""GTK editor view with inline image rendering."""
from __future__ import annotations

from dataclasses import dataclass
import base64
import mimetypes
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango  # type: ignore

from config import AppConfig
from editor_document import DocumentModel
from editor_segments import ImageSegment, Segment, TextSegment
from services_image_cache import materialize_data_uri


@dataclass
class InlineImageNode:
    """Model describing an inline image in the text flow."""

    path: Path
    status: str
    widget: Gtk.Widget
    cols: int


class EditorView:
    """Encapsulates the Gtk.TextView and inline image rendering."""

    MAX_COLS = 88

    def __init__(self, window: Gtk.ApplicationWindow, config: AppConfig) -> None:
        self._window = window
        self._config = config
        self._inline_images: dict[Gtk.TextChildAnchor, InlineImageNode] = {}
        self._document: DocumentModel | None = None
        self._cursor_mode: str = "insert"
        self._cursor_tag: Gtk.TextTag | None = None
        self._cursor_tag_range: tuple[int, int] | None = None
        self._suppress_insert_handler = False

        scroller = Gtk.ScrolledWindow()
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        self._scroller = scroller

        text_view = Gtk.TextView()
        text_view.set_wrap_mode(Gtk.WrapMode.NONE)
        text_view.set_monospace(True)
        self._apply_font(text_view)
        self._apply_tab_width(text_view)
        self._text_view = text_view
        scroller.set_child(text_view)

        buffer = text_view.get_buffer()
        self._cursor_tag = buffer.create_tag(
            "cursor-block",
            background="white",
            foreground="black",
            background_full_height=True,
        )

        overlay = Gtk.Overlay()
        overlay.set_hexpand(True)
        overlay.set_vexpand(True)
        overlay.set_child(scroller)
        self._overlay = overlay

        cursor_layer = Gtk.DrawingArea()
        cursor_layer.set_hexpand(True)
        cursor_layer.set_vexpand(True)
        cursor_layer.set_can_target(False)
        cursor_layer.set_draw_func(self._draw_cursor)
        overlay.add_overlay(cursor_layer)
        self._cursor_layer = cursor_layer

        buffer.connect("mark-set", self._on_buffer_mark_set)
        buffer.connect("insert-text", self._on_buffer_insert_text)

    @property
    def widget(self) -> Gtk.Widget:
        return self._overlay

    def add_key_controller(self, controller: Gtk.EventControllerKey) -> None:
        self._text_view.add_controller(controller)

    def grab_focus(self) -> None:
        self._text_view.grab_focus()

    def set_editable(self, editable: bool) -> None:
        self._text_view.set_editable(editable)

    def set_cursor_mode(self, mode: str) -> None:
        self._cursor_mode = mode
        self._text_view.set_cursor_visible(False)
        self._queue_cursor_draw()

    def set_text(self, text: str) -> None:
        buffer = self._text_view.get_buffer()
        buffer.set_text(text)

    def clear(self) -> None:
        buffer = self._text_view.get_buffer()
        buffer.set_text("")

    def insert_image(self, path: Path) -> None:
        """Insert an inline image node at the caret position."""
        buffer = self._text_view.get_buffer()
        insert_iter = buffer.get_iter_at_mark(buffer.get_insert())
        insert_iter = self._ensure_image_fits_line(buffer, insert_iter, path)
        cols = self._estimate_image_cols(path)
        anchor = self._insert_inline_image_at_iter(path, insert_iter, cols)
        after_iter = insert_iter.copy()
        if after_iter.forward_char():
            buffer.place_cursor(after_iter)
        self._text_view.grab_focus()
        if anchor is not None:
            GLib.idle_add(self._load_inline_image, anchor, path)

    def handle_inline_image_delete(self, key_name: str) -> bool:
        buffer = self._text_view.get_buffer()
        cursor_iter = buffer.get_iter_at_mark(buffer.get_insert())
        target_iter = cursor_iter.copy()
        if key_name == "BackSpace":
            if not target_iter.backward_char():
                return False
        anchor = target_iter.get_child_anchor()
        if not anchor:
            return False
        self._remove_inline_anchor(anchor)
        end_iter = target_iter.copy()
        if end_iter.forward_char():
            buffer.delete(target_iter, end_iter)
        return True

    def search_next(self, term: str) -> bool:
        if not term:
            return False
        buffer = self._text_view.get_buffer()
        insert_iter = buffer.get_iter_at_mark(buffer.get_insert())
        match = insert_iter.forward_search(term, 0, None)
        if match is None:
            start_iter = buffer.get_start_iter()
            match = start_iter.forward_search(term, 0, None)
        if match is None:
            return False
        match_start, match_end = match
        buffer.select_range(match_start, match_end)
        buffer.place_cursor(match_end)
        self._text_view.scroll_to_iter(match_start, 0.2, False, 0.0, 0.0)
        return True

    def extract_segments(self) -> list[Segment]:
        buffer = self._text_view.get_buffer()
        anchors = list(self._inline_images.keys())
        anchor_positions: list[tuple[int, Gtk.TextChildAnchor]] = []
        for anchor in anchors:
            try:
                iter_at = buffer.get_iter_at_child_anchor(anchor)
            except Exception:
                continue
            anchor_positions.append((iter_at.get_offset(), anchor))
        anchor_positions.sort(key=lambda item: item[0])

        start_iter = buffer.get_start_iter()
        segments: list[Segment] = []
        current_iter = start_iter.copy()

        for offset, anchor in anchor_positions:
            anchor_iter = buffer.get_iter_at_offset(offset)
            if current_iter.get_offset() < anchor_iter.get_offset():
                text = buffer.get_text(current_iter, anchor_iter, True)
                if text:
                    segments.append(TextSegment(text))
            node = self._inline_images.get(anchor)
            if node:
                data_uri = self._image_to_data_uri(node.path)
                if data_uri:
                    segments.append(ImageSegment(data_uri, node.path.name))
            current_iter = anchor_iter.copy()

        end_iter = buffer.get_end_iter()
        if current_iter.get_offset() < end_iter.get_offset():
            trailing = buffer.get_text(current_iter, end_iter, True)
            if trailing:
                segments.append(TextSegment(trailing))

        if not segments:
            segments.append(TextSegment(""))
        return segments

    def load_segments(self, segments: list[Segment]) -> None:
        buffer = self._text_view.get_buffer()
        buffer.set_text("")
        self._inline_images.clear()
        for segment in segments:
            if isinstance(segment, TextSegment):
                buffer.insert(buffer.get_end_iter(), segment.text)
            elif isinstance(segment, ImageSegment):
                image_path = materialize_data_uri(segment.data_uri)
                if image_path:
                    end_iter = buffer.get_end_iter()
                    end_iter = self._ensure_image_fits_line(buffer, end_iter, image_path)
                    cols = self._estimate_image_cols(image_path)
                    anchor = self._insert_inline_image_at_iter(image_path, end_iter, cols)
                    if anchor is not None:
                        GLib.idle_add(self._load_inline_image, anchor, image_path)

    def set_document(self, document: DocumentModel) -> None:
        self._document = document
        document.add_listener(lambda doc: self.load_segments(doc.get_segments()))
        self.load_segments(document.get_segments())
        self._queue_cursor_draw()

    def get_cursor_offset(self) -> int:
        buffer = self._text_view.get_buffer()
        insert_iter = buffer.get_iter_at_mark(buffer.get_insert())
        return insert_iter.get_offset()

    def clear_selection(self) -> None:
        buffer = self._text_view.get_buffer()
        insert_iter = buffer.get_iter_at_mark(buffer.get_insert())
        buffer.select_range(insert_iter, insert_iter)
        if self._document:
            self._document.clear_selection()
        self._queue_cursor_draw()

    def begin_visual_selection(self) -> None:
        if not self._document:
            return
        offset = self.get_cursor_offset()
        self._document.set_selection(offset, offset)
        self._queue_cursor_draw()

    def move_cursor(self, direction: str, extend_selection: bool) -> bool:
        buffer = self._text_view.get_buffer()
        insert_iter = buffer.get_iter_at_mark(buffer.get_insert())
        current_offset = insert_iter.get_offset()

        new_iter = insert_iter.copy()
        moved = False
        if direction == "h":
            moved = new_iter.backward_char()
        elif direction == "l":
            moved = new_iter.forward_char()
        elif direction == "j":
            moved = new_iter.forward_line()
        elif direction == "k":
            moved = new_iter.backward_line()
        if not moved:
            return False

        buffer.place_cursor(new_iter)

        if extend_selection:
            anchor_offset = current_offset
            if self._document:
                sel_start, _sel_end = self._document.get_selection()
                if sel_start is not None:
                    anchor_offset = sel_start
            anchor_iter = buffer.get_iter_at_offset(anchor_offset)
            buffer.select_range(anchor_iter, new_iter)
            if self._document:
                self._document.set_selection(anchor_iter.get_offset(), new_iter.get_offset())
        else:
            buffer.select_range(new_iter, new_iter)
            if self._document:
                self._document.clear_selection()

        self._text_view.scroll_to_iter(new_iter, 0.2, False, 0.0, 0.0)
        self._queue_cursor_draw()
        return True

    def _on_buffer_mark_set(self, _buffer: Gtk.TextBuffer, _iter: Gtk.TextIter, _mark: Gtk.TextMark) -> None:
        self._queue_cursor_draw()

    def _queue_cursor_draw(self) -> None:
        self._update_cursor_block_tag()
        self._cursor_layer.queue_draw()

    def _draw_cursor(self, _area: Gtk.DrawingArea, ctx, _width: int, _height: int) -> None:
        if self._cursor_tag_range is not None:
            return
        rect = self._compute_cursor_rect()
        if rect is None:
            return
        x, y, w, h = rect
        ctx.set_source_rgba(1.0, 1.0, 1.0, 1.0)
        ctx.rectangle(x, y, w, h)
        ctx.fill()

    def _compute_cursor_rect(self) -> tuple[float, float, float, float] | None:
        buffer = self._text_view.get_buffer()
        insert_iter = buffer.get_iter_at_mark(buffer.get_insert())
        location = self._text_view.get_iter_location(insert_iter)
        if location.height == 0:
            line_iter = insert_iter.copy()
            line_iter.set_line_offset(0)
            line_y, line_height = self._text_view.get_line_yrange(line_iter)
            if line_height == 0:
                line_height = self._get_line_height()
            location.y = line_y
            location.height = line_height
        x, y = self._text_view.buffer_to_window_coords(
            Gtk.TextWindowType.TEXT,
            location.x,
            location.y,
        )
        translated = self._text_view.translate_coordinates(self._overlay, x, y)
        if translated is None:
            return None
        x, y = translated
        cell_width = self._get_cell_width()
        if cell_width <= 0:
            cell_width = max(1.0, float(location.width))
        return float(x), float(y), float(cell_width), float(location.height)

    def _get_cell_width_for_view(self, text_view: Gtk.TextView) -> float:
        context = text_view.get_pango_context()
        desc = context.get_font_description()
        metrics = context.get_metrics(desc, context.get_language())
        return metrics.get_approximate_char_width() / Pango.SCALE

    def _get_cell_width(self) -> float:
        return self._get_cell_width_for_view(self._text_view)

    def _apply_font(self, text_view: Gtk.TextView) -> None:
        if not self._config.font_family and not self._config.font_size:
            return
        font_parts: list[str] = []
        if self._config.font_family:
            font_parts.append(f"font-family: {self._config.font_family};")
        if self._config.font_size:
            font_parts.append(f"font-size: {self._config.font_size}px;")
        rules = " ".join(font_parts)
        css = f"""
        textview.editor-font {{ {rules} }}
        textview.editor-font text {{ {rules} }}
        """
        text_view.add_css_class("editor-font")
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode("utf-8"))
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _apply_tab_width(self, text_view: Gtk.TextView) -> None:
        cell_width = self._get_cell_width_for_view(text_view)
        if cell_width <= 0:
            return
        tab_width = int(cell_width * max(1, self._config.tab_width))
        tabs = Pango.TabArray(1, True)
        tabs.set_tab(0, Pango.TabAlign.LEFT, tab_width)
        text_view.set_tabs(tabs)

    def _get_line_height(self) -> int:
        context = self._text_view.get_pango_context()
        desc = context.get_font_description()
        metrics = context.get_metrics(desc, context.get_language())
        height = (metrics.get_ascent() + metrics.get_descent()) / Pango.SCALE
        return max(1, int(height))

    def _on_buffer_insert_text(
        self, buffer: Gtk.TextBuffer, insert_iter: Gtk.TextIter, text: str, length: int
    ) -> None:
        if self._suppress_insert_handler:
            return
        if not self._text_view.get_editable():
            return
        if self.MAX_COLS <= 0:
            return
        self._suppress_insert_handler = True
        buffer.stop_emission_by_name("insert-text")
        try:
            line = insert_iter.get_line()
            line_text_len = insert_iter.get_chars_in_line()
            line_image_cols = self._get_image_cols_for_line(line)
            line_total_cols = line_text_len + line_image_cols
            remaining_after = line_total_cols - self._get_visual_col_at_iter(insert_iter)
            col = self._get_visual_col_at_iter(insert_iter)
            out_chars: list[str] = []
            for ch in text:
                if ch == "\n":
                    out_chars.append(ch)
                    col = 0
                    remaining_after = 0
                    continue
                if col >= self.MAX_COLS or (remaining_after > 0 and col + remaining_after >= self.MAX_COLS):
                    out_chars.append("\n")
                    col = 0
                    remaining_after = 0
                out_chars.append(ch)
                col += 1
            buffer.insert(insert_iter, "".join(out_chars))
        finally:
            self._suppress_insert_handler = False

    def _update_cursor_block_tag(self) -> None:
        if not self._cursor_tag:
            return
        buffer = self._text_view.get_buffer()
        insert_iter = buffer.get_iter_at_mark(buffer.get_insert())
        start_offset = insert_iter.get_offset()
        end_iter = insert_iter.copy()
        has_char = end_iter.forward_char()
        if not has_char or end_iter.get_char() == "\n":
            if self._cursor_tag_range:
                old_start, old_end = self._cursor_tag_range
                buffer.remove_tag(
                    self._cursor_tag,
                    buffer.get_iter_at_offset(old_start),
                    buffer.get_iter_at_offset(old_end),
                )
                self._cursor_tag_range = None
            return
        end_offset = end_iter.get_offset()
        if self._cursor_tag_range == (start_offset, end_offset):
            return
        if self._cursor_tag_range:
            old_start, old_end = self._cursor_tag_range
            buffer.remove_tag(
                self._cursor_tag,
                buffer.get_iter_at_offset(old_start),
                buffer.get_iter_at_offset(old_end),
            )
        buffer.apply_tag(self._cursor_tag, insert_iter, end_iter)
        self._cursor_tag_range = (start_offset, end_offset)

    def _build_inline_image_widget(self, path: Path) -> Gtk.Widget:
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.NONE)
        stack.set_halign(Gtk.Align.START)
        stack.set_valign(Gtk.Align.BASELINE)

        loading_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        loading_box.set_halign(Gtk.Align.START)
        loading_box.set_valign(Gtk.Align.CENTER)
        spinner = Gtk.Spinner()
        spinner.start()
        loading_label = Gtk.Label(label=f"Loading {path.name}...")
        loading_label.set_xalign(0.0)
        loading_box.append(spinner)
        loading_box.append(loading_label)

        error_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        error_box.set_halign(Gtk.Align.START)
        error_box.set_valign(Gtk.Align.CENTER)
        error_icon = Gtk.Image.new_from_icon_name("dialog-error")
        error_icon.set_pixel_size(16)
        error_label = Gtk.Label(label=f"Failed to load {path.name}")
        error_label.set_xalign(0.0)
        error_box.append(error_icon)
        error_box.append(error_label)

        image_widget = Gtk.Picture()
        image_widget.set_can_shrink(False)
        image_widget.set_content_fit(Gtk.ContentFit.CONTAIN)
        image_widget.set_halign(Gtk.Align.START)
        image_widget.set_valign(Gtk.Align.BASELINE)
        image_widget.add_css_class("inline-image")

        stack.add_named(loading_box, "loading")
        stack.add_named(image_widget, "ready")
        stack.add_named(error_box, "error")
        stack.set_visible_child_name("loading")
        return stack

    def _insert_inline_image_at_iter(
        self, path: Path, insert_iter: Gtk.TextIter, cols: int
    ) -> Gtk.TextChildAnchor | None:
        buffer = self._text_view.get_buffer()
        anchor = buffer.create_child_anchor(insert_iter)
        widget = self._build_inline_image_widget(path)
        self._text_view.add_child_at_anchor(widget, anchor)
        self._inline_images[anchor] = InlineImageNode(
            path=path,
            status="loading",
            widget=widget,
            cols=cols,
        )
        return anchor

    def _load_inline_image(self, anchor: Gtk.TextChildAnchor, path: Path) -> bool:
        node = self._inline_images.get(anchor)
        if not node:
            return False
        stack = node.widget
        if not isinstance(stack, Gtk.Stack):
            return False
        try:
            pixbuf = self._load_pixbuf(path)
        except (GLib.Error, OSError):
            node.status = "error"
            stack.set_visible_child_name("error")
            return False
        image_widget = stack.get_child_by_name("ready")
        if isinstance(image_widget, Gtk.Picture):
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            image_widget.set_paintable(texture)
            image_widget.set_size_request(pixbuf.get_width(), pixbuf.get_height())
        node.status = "ready"
        stack.set_visible_child_name("ready")
        return False

    def _load_pixbuf(self, path: Path) -> GdkPixbuf.Pixbuf:
        max_width = self._get_image_max_width()
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(path.as_posix())
        if pixbuf.get_width() <= max_width:
            return pixbuf
        ratio = max_width / pixbuf.get_width()
        new_height = max(1, int(pixbuf.get_height() * ratio))
        return pixbuf.scale_simple(max_width, new_height, GdkPixbuf.InterpType.BILINEAR)

    def _get_image_max_width(self) -> int:
        window_width = self._window.get_width() if self._window else 0
        if window_width and window_width > 200:
            max_width = max(320, min(1200, window_width - 120))
        else:
            max_width = 900
        cell_width = self._get_cell_width()
        if cell_width > 0:
            max_cols_width = int(cell_width * self.MAX_COLS)
            if max_cols_width > 0:
                max_width = min(max_width, max_cols_width)
        return max_width

    def _estimate_image_cols(self, path: Path) -> int:
        cell_width = self._get_cell_width()
        if cell_width <= 0:
            return 1
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(path.as_posix())
        except (GLib.Error, OSError):
            return 1
        max_width = self._get_image_max_width()
        scaled_width = min(pixbuf.get_width(), max_width)
        return max(1, int((scaled_width + cell_width - 1) // cell_width))

    def _get_image_cols_for_line(self, line: int) -> int:
        buffer = self._text_view.get_buffer()
        cols = 0
        for anchor, node in self._inline_images.items():
            try:
                iter_at = buffer.get_iter_at_child_anchor(anchor)
            except Exception:
                continue
            if iter_at.get_line() == line:
                cols += max(1, node.cols)
        return cols

    def _get_image_cols_before_iter(self, iter_at: Gtk.TextIter) -> int:
        buffer = self._text_view.get_buffer()
        cols = 0
        line = iter_at.get_line()
        offset = iter_at.get_offset()
        for anchor, node in self._inline_images.items():
            try:
                anchor_iter = buffer.get_iter_at_child_anchor(anchor)
            except Exception:
                continue
            if anchor_iter.get_line() == line and anchor_iter.get_offset() <= offset:
                cols += max(1, node.cols)
        return cols

    def _get_visual_col_at_iter(self, iter_at: Gtk.TextIter) -> int:
        text_col = iter_at.get_line_offset()
        image_cols = self._get_image_cols_before_iter(iter_at)
        return text_col + image_cols

    def _ensure_image_fits_line(
        self, buffer: Gtk.TextBuffer, insert_iter: Gtk.TextIter, path: Path
    ) -> Gtk.TextIter:
        image_cols = self._estimate_image_cols(path)
        current_col = self._get_visual_col_at_iter(insert_iter)
        remaining = self.MAX_COLS - current_col
        if current_col > 0 and image_cols > remaining:
            buffer.insert(insert_iter, "\n")
            return buffer.get_iter_at_mark(buffer.get_insert())
        return insert_iter

    def _remove_inline_anchor(self, anchor: Gtk.TextChildAnchor) -> None:
        node = self._inline_images.pop(anchor, None)
        if node and node.widget:
            node.widget.destroy()

    def _image_to_data_uri(self, path: Path) -> str | None:
        try:
            data = path.read_bytes()
        except OSError:
            return None
        mime_type, _ = mimetypes.guess_type(path.as_posix())
        if not mime_type:
            mime_type = "image/png"
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
