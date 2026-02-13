from __future__ import annotations

import hashlib
import os
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
from latex_template import render_latex_html
from map_template import render_map_html
from three_template import render_three_html


class BlockEditorView(Gtk.ScrolledWindow):
    def __init__(self) -> None:
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.set_can_focus(True)
        self.set_propagate_natural_height(False)
        self.set_propagate_natural_width(False)

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

        self.set_child(self._column)

    def set_document(self, document: BlockDocument) -> None:
        for child in list(self._column):
            self._column.remove(child)

        self._block_widgets = []

        toc_text = _build_toc(
            [block for block in document.blocks if isinstance(block, TextBlock)]
        )
        for block in document.blocks:
            if isinstance(block, TextBlock):
                text = toc_text if block.kind == "toc" else block.text
                widget = _TextBlockView(text, block.kind)
            elif isinstance(block, ThreeBlock):
                widget = _ThreeBlockView(block.source)
            elif isinstance(block, PythonImageBlock):
                widget = _PyImageBlockView(block)
            elif isinstance(block, LatexBlock):
                widget = _LatexBlockView(block.source)
            elif isinstance(block, MapBlock):
                widget = _MapBlockView(block.source)
            else:
                continue
            self._block_widgets.append(widget)
            self._column.append(widget)

        self._selected_index = min(
            self._selected_index, max(len(self._block_widgets) - 1, 0)
        )
        self._refresh_selection()
        self._column.queue_resize()
        GLib.idle_add(self._column.queue_resize)


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

    def get_scroll_position(self) -> float:
        vadjustment = self.get_vadjustment()
        if vadjustment is None:
            return 0.0
        return vadjustment.get_value()

    def set_scroll_position(self, value: float) -> None:
        vadjustment = self.get_vadjustment()
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
            self._scroll_to_selected()

    def center_on_index(self, index: int) -> None:
        if not self._block_widgets:
            return
        if index < 0 or index >= len(self._block_widgets):
            return
        widget = self._block_widgets[index]
        allocation = widget.get_allocation()
        vadjustment = self.get_vadjustment()
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
        if from_index >= len(self._block_widgets) or to_index >= len(self._block_widgets):
            return
        if from_index == to_index:
            return
        widget = self._block_widgets.pop(from_index)
        self._block_widgets.insert(to_index, widget)
        self._column.remove(widget)
        self._column.insert_child_after(widget, self._block_widgets[to_index - 1] if to_index > 0 else None)
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
            self._help_scroll = self.get_vadjustment().get_value() if self.get_vadjustment() else 0.0
            self._help_selected = self._selected_index
            self.set_child(self._help_panel)
            self._help_panel.grab_focus()
        else:
            self.set_child(self._column)
            GLib.idle_add(self._restore_help_state)

    def _restore_help_state(self) -> bool:
        self.set_selected_index(self._help_selected, scroll=False)
        self.set_scroll_position(self._help_scroll)
        return False

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
        if self._selected_index == len(self._block_widgets) - 1:
            bottom += 120
        view_top = vadjustment.get_value()
        view_bottom = view_top + vadjustment.get_page_size()
        if top < view_top:
            vadjustment.set_value(max(0, top - 12))
        elif bottom > view_bottom:
            vadjustment.set_value(max(0, bottom - vadjustment.get_page_size() + 12))

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
            "  g/G        first/last block",
            "  Enter      edit selected block",
            "  q          quit without saving",
            "",
            "Blocks",
            "  ,n         normal text",
            "  ,ht        title",
            "  ,h1 ,h2 ,h3 headings",
            "  ,toc       table of contents",
            "  ,js        Three.js block",
            "  ,py        Python render",
            "  ,ltx       LaTeX block",
            "  ,map       map block",
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


class _ThreeBlockView(Gtk.Frame):
    def __init__(self, source: str) -> None:
        super().__init__()
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

        source = render_three_html(source).replace(
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
        background.red = 0.0
        background.green = 0.0
        background.blue = 0.0
        background.alpha = 0.0
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
    def __init__(self, source: str) -> None:
        super().__init__()
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
        background = Gdk.RGBA()
        background.red = 0.0
        background.green = 0.0
        background.blue = 0.0
        background.alpha = 0.0
        if hasattr(view, "set_background_color"):
            view.set_background_color(background)
        view.set_vexpand(False)
        view.set_hexpand(True)
        view.set_size_request(-1, 80)
        view.set_valign(Gtk.Align.START)
        self._html = render_latex_html(source)
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
    def __init__(self, source: str) -> None:
        super().__init__()
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
        background = Gdk.RGBA()
        background.red = 0.0
        background.green = 0.0
        background.blue = 0.0
        background.alpha = 0.0
        if hasattr(view, "set_background_color"):
            view.set_background_color(background)
        view.set_vexpand(False)
        view.set_hexpand(True)
        view.set_size_request(-1, 320)
        self._html = render_map_html(source)
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
        if isinstance(block, TextBlock) and block.kind in {"title", "h1", "h2", "h3"}:
            text = block.text.strip().splitlines()[0] if block.text.strip() else ""
            if text:
                headings.append((block.kind, text))

    if not headings:
        return "Table of Contents\n\n(No headings yet)"

    lines = ["Table of Contents", ""]
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
