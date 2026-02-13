from __future__ import annotations

import hashlib
import os
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
from gi.repository import Gdk, Gtk  # type: ignore[import-not-found, attr-defined]
try:
    from gi.repository import WebKit  # type: ignore[import-not-found, attr-defined]
except Exception:
    WebKit = None

from block_model import (
    BlockDocument,
    ImageBlock,
    LatexBlock,
    PythonImageBlock,
    TextBlock,
    ThreeBlock,
)
from latex_template import render_latex_html


class BlockEditorView(Gtk.ScrolledWindow):
    def __init__(self) -> None:
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.set_can_focus(True)
        self.set_propagate_natural_height(False)
        self.set_propagate_natural_width(False)

        self._block_widgets: list[Gtk.Widget] = []
        self._selected_index = 0

        self._column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._column.set_margin_top(24)
        self._column.set_margin_bottom(24)
        self._column.set_margin_start(24)
        self._column.set_margin_end(24)
        self._column.set_valign(Gtk.Align.START)

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
            elif isinstance(block, ThreeBlock):
                widget = _ThreeBlockView(block.source)
            elif isinstance(block, PythonImageBlock):
                widget = _PyImageBlockView(block)
            elif isinstance(block, LatexBlock):
                widget = _LatexBlockView(block.source)
            else:
                continue
            self._block_widgets.append(widget)
            self._column.append(widget)

        self._selected_index = min(
            self._selected_index, max(len(self._block_widgets) - 1, 0)
        )
        self._refresh_selection()

    def move_selection(self, delta: int) -> None:
        if not self._block_widgets:
            return
        self._selected_index = max(
            0, min(self._selected_index + delta, len(self._block_widgets) - 1)
        )
        self._refresh_selection()
        self._scroll_to_selected()

    def select_first(self) -> None:
        if not self._block_widgets:
            return
        self._selected_index = 0
        self._refresh_selection()
        self._scroll_to_selected()

    def select_last(self) -> None:
        if not self._block_widgets:
            return
        self._selected_index = len(self._block_widgets) - 1
        self._refresh_selection()
        self._scroll_to_selected()

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

    def _scroll_to_selected(self) -> None:
        if not self._block_widgets:
            return
        widget = self._block_widgets[self._selected_index]
        allocation = widget.get_allocation()
        vadjustment = self.get_vadjustment()
        if vadjustment is None:
            return
        top = allocation.y
        bottom = allocation.y + allocation.height
        view_top = vadjustment.get_value()
        view_bottom = view_top + vadjustment.get_page_size()
        if top < view_top:
            vadjustment.set_value(max(0, top - 12))
        elif bottom > view_bottom:
            vadjustment.set_value(max(0, bottom - vadjustment.get_page_size() + 12))


class _TextBlockView(Gtk.Frame):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.add_css_class("block")
        self.add_css_class("block-text")

        self._text_view = Gtk.TextView()
        self._text_view.set_monospace(True)
        self._text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._text_view.set_top_margin(8)
        self._text_view.set_bottom_margin(0)
        self._text_view.set_left_margin(12)
        self._text_view.set_right_margin(12)
        self._text_view.set_pixels_above_lines(0)
        self._text_view.set_pixels_below_lines(0)
        self._text_view.set_pixels_inside_wrap(0)
        self._text_view.set_editable(False)
        self._text_view.set_cursor_visible(False)

        buffer = self._text_view.get_buffer()
        buffer.set_text(text)

        self.set_child(self._text_view)


class _ImageBlockView(Gtk.Frame):
    def __init__(self, path: str, alt: str) -> None:
        super().__init__()
        self.add_css_class("block")
        self.add_css_class("block-image")

        if os.path.exists(path):
            picture = Gtk.Picture.new_for_filename(path)
            picture.set_can_shrink(False)
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            picture.set_margin_top(12)
            picture.set_margin_bottom(12)
            picture.set_margin_start(12)
            picture.set_margin_end(12)
            picture.set_valign(Gtk.Align.START)
            self.set_child(picture)
        else:
            label = Gtk.Label(label=f"Missing image: {alt or path}")
            label.set_margin_top(12)
            label.set_margin_bottom(12)
            label.set_margin_start(12)
            label.set_margin_end(12)
            self.set_child(label)


class _ThreeBlockView(Gtk.Frame):
    def __init__(self, source: str) -> None:
        super().__init__()
        self.add_css_class("block")
        self.add_css_class("block-three")

        if WebKit is None:
            label = Gtk.Label(label="WebKitGTK not available for 3D blocks")
            label.set_margin_top(12)
            label.set_margin_bottom(12)
            label.set_margin_start(12)
            label.set_margin_end(12)
            self.set_child(label)
            return

        if not source.strip():
            label = Gtk.Label(label="Empty 3D block")
            label.set_margin_top(12)
            label.set_margin_bottom(12)
            label.set_margin_start(12)
            label.set_margin_end(12)
            self.set_child(label)
            return

        source = source.replace("__GTKV_THREE_SRC__", _three_module_uri())

        view = WebKit.WebView()
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
        background.red = 0.0
        background.green = 0.0
        background.blue = 0.0
        background.alpha = 0.0
        if hasattr(view, "set_background_color"):
            view.set_background_color(background)
        view.set_vexpand(False)
        view.set_hexpand(True)
        view.set_size_request(-1, 300)
        view.load_html(source, "file:///")
        self.set_child(view)


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
            box.set_margin_top(12)
            box.set_margin_bottom(12)
            box.set_margin_start(12)
            box.set_margin_end(12)
            box.add_css_class("pyimage-container")
            box.append(picture)
            self.set_child(box)
            return

        label_text = "Python render pending"
        if block.last_error:
            label_text = f"Python render error: {block.last_error}"
        label = Gtk.Label(label=label_text)
        label.set_margin_top(12)
        label.set_margin_bottom(12)
        label.set_margin_start(12)
        label.set_margin_end(12)
        self.set_child(label)


class _LatexBlockView(Gtk.Frame):
    def __init__(self, source: str) -> None:
        super().__init__()
        self.add_css_class("block")
        self.add_css_class("block-three")

        if WebKit is None:
            label = Gtk.Label(label="WebKitGTK not available for LaTeX blocks")
            label.set_margin_top(12)
            label.set_margin_bottom(12)
            label.set_margin_start(12)
            label.set_margin_end(12)
            self.set_child(label)
            return

        if not source.strip():
            label = Gtk.Label(label="Empty LaTeX block")
            label.set_margin_top(12)
            label.set_margin_bottom(12)
            label.set_margin_start(12)
            label.set_margin_end(12)
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
        background = Gdk.RGBA()
        background.red = 0.0
        background.green = 0.0
        background.blue = 0.0
        background.alpha = 0.0
        if hasattr(view, "set_background_color"):
            view.set_background_color(background)
        view.set_vexpand(False)
        view.set_hexpand(True)
        view.set_size_request(-1, 240)
        view.load_html(render_latex_html(source), "file:///")
        self.set_child(view)


def _three_module_uri() -> str:
    bundled = Path(__file__).with_name("three.module.min.js")
    return bundled.resolve().as_uri()


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
