"""Application orchestrator coordinating UI, editor state, and image handling."""
from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import html
import mimetypes
import os
import shlex
import shutil
import subprocess
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional, cast

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk  # type: ignore

from config import AppConfig


@dataclass
class EditorState:
    """Minimal editor state placeholder for Vim-like mode handling."""

    mode: str = "normal"
    file_path: Optional[Path] = None


@dataclass
class InlineImageNode:
    """Model describing an inline image in the text flow."""

    path: Path
    status: str
    widget: Gtk.Widget


class Orchestrator:
    """Coordinates GTK widgets, editor state, and command handling."""

    def __init__(self, application: Gtk.Application, window: Gtk.ApplicationWindow, config: AppConfig) -> None:
        self._application = application
        self._window = window
        self._config = config
        self._state = EditorState()

        self._root: Optional[Gtk.Box] = None
        self._text_view: Optional[Gtk.TextView] = None
        self._status_label: Optional[Gtk.Label] = None
        self._inline_images: dict[Gtk.TextChildAnchor, InlineImageNode] = {}

    def start(self) -> None:
        """Initialize UI, connect signals, and load initial document."""
        self._build_ui()
        self._connect_events()
        if self._config.startup_file:
            self.load_document(Path(self._config.startup_file))
        self._update_status()

    def _build_ui(self) -> None:
        root = cast(Gtk.Box, Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0))
        self._root = root
        self._window.set_child(root)

        self._apply_transparent_theme()

        scroller = Gtk.ScrolledWindow()
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        root.append(scroller)

        text_view = cast(Gtk.TextView, Gtk.TextView())
        text_view.set_wrap_mode(Gtk.WrapMode.NONE)
        text_view.set_monospace(True)
        self._text_view = text_view
        scroller.set_child(text_view)

        status_label = cast(Gtk.Label, Gtk.Label(label=""))
        status_label.set_xalign(0.0)
        self._status_label = status_label
        root.append(status_label)

    def _connect_events(self) -> None:
        if not self._text_view:
            return
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key_pressed)
        self._text_view.add_controller(controller)

    def _on_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        key_name = Gdk.keyval_name(keyval) or ""
        if self._is_ctrl_i(state, key_name):
            self._open_image_chooser()
            return True
        if self._is_ctrl_s(state, key_name):
            self._handle_save_request()
            return True
        if self._state.mode == "normal":
            return self._handle_normal_mode(key_name)
        if self._state.mode == "insert":
            return self._handle_insert_mode(key_name)
        return False

    def _is_ctrl_i(self, state: Gdk.ModifierType, key_name: str) -> bool:
        return key_name.lower() == "i" and bool(state & Gdk.ModifierType.CONTROL_MASK)

    def _is_ctrl_s(self, state: Gdk.ModifierType, key_name: str) -> bool:
        return key_name.lower() == "s" and bool(state & Gdk.ModifierType.CONTROL_MASK)

    def _open_image_chooser(self) -> None:
        if self._config.file_selector.lower() == "o":
            if self._begin_image_selector_o():
                if self._text_view:
                    self._text_view.grab_focus()
                return
        self._open_image_selector_gtk()

    def _open_image_selector_gtk(self) -> None:
        downloads_dir = Path.home() / "Downloads"
        dialog = Gtk.FileDialog()
        dialog.set_title("Insert Image")
        dialog.set_modal(True)
        dialog.set_initial_folder(Gio.File.new_for_path(downloads_dir.as_posix()))

        image_filter = Gtk.FileFilter()
        image_filter.set_name("Images")
        image_filter.add_mime_type("image/*")
        image_filter.add_pattern("*.png")
        image_filter.add_pattern("*.jpg")
        image_filter.add_pattern("*.jpeg")
        image_filter.add_pattern("*.gif")
        image_filter.add_pattern("*.bmp")
        image_filter.add_pattern("*.webp")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(image_filter)
        dialog.set_filters(filters)
        dialog.set_default_filter(image_filter)

        def _on_opened(_dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
            try:
                file = _dialog.open_finish(result)
            except GLib.Error:
                return
            if not file:
                return
            path = file.get_path()
            if path:
                self.insert_image(Path(path))
                if self._text_view:
                    self._text_view.grab_focus()

        dialog.open(self._window, None, _on_opened)

    def _begin_image_selector_o(self) -> bool:
        if shutil.which("o") is None:
            return False
        downloads_dir = Path.home() / "Downloads"
        start_dir = downloads_dir if downloads_dir.exists() else Path.home()
        cache_path = self._get_o_picker_cache_path()
        if cache_path and cache_path.exists():
            try:
                cache_path.unlink()
            except OSError:
                pass
        cmd = [
            "o",
            "-p",
            start_dir.as_posix(),
            "-lf",
            "png,jpg,jpeg,gif,bmp,webp",
        ]
        self._set_status_hint("PICKER  Hit ENTER to select file")
        if not self._launch_terminal(cmd, cwd=start_dir):
            return False
        if not cache_path:
            return False
        self._poll_for_o_picker_selection(cache_path)
        return True

    def _launch_terminal(self, command: list[str], cwd: Path | None = None) -> bool:
        commands: list[list[str]] = []
        term_env = os.environ.get("TERMINAL")
        if term_env:
            commands.append(shlex.split(term_env))
        commands.extend(
            [
                [cmd]
                for cmd in (
                    "alacritty",
                    "foot",
                    "kitty",
                    "wezterm",
                    "gnome-terminal",
                    "xterm",
                )
            ]
        )

        cmd_joined = shlex.join(command)
        for cmd in commands:
            if not cmd:
                continue
            if shutil.which(cmd[0]) is None:
                continue
            launch_cmd = list(cmd)
            if any("{cmd}" in token for token in launch_cmd):
                launch_cmd = [token.replace("{cmd}", cmd_joined) for token in launch_cmd]
            else:
                launch_cmd.extend(["-e"] + command)
            try:
                process = subprocess.Popen(
                    launch_cmd,
                    cwd=cwd.as_posix() if cwd else None,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            except OSError:
                continue
            return True
        return False

    @staticmethod
    def _get_o_picker_cache_path() -> Path | None:
        cache_root = os.environ.get("XDG_CACHE_HOME")
        if cache_root:
            return Path(cache_root) / "o" / "picker-selection.txt"
        return Path.home() / ".cache" / "o" / "picker-selection.txt"

    def _poll_for_o_picker_selection(self, cache_path: Path) -> None:
        start_time = time.monotonic()
        allowed_exts = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}

        def _check() -> bool:
            if cache_path.exists():
                try:
                    data = cache_path.read_text(encoding="utf-8").strip()
                except OSError:
                    return False
                if not data:
                    return False
                first = data.splitlines()[0].strip()
                if not first:
                    return False
                path = Path(first)
                if path.exists() and path.is_file():
                    ext = path.suffix.lstrip(".").lower()
                    if ext in allowed_exts:
                        self.insert_image(path)
                        if self._text_view:
                            self._text_view.grab_focus()
                        self._update_status()
                return False
            if time.monotonic() - start_time > 300:
                self._update_status()
                return False
            return True

        GLib.timeout_add(200, _check)

    def _poll_for_o_save_path(self, cache_path: Path) -> None:
        start_time = time.monotonic()

        def _check() -> bool:
            if cache_path.exists():
                try:
                    data = cache_path.read_text(encoding="utf-8").strip()
                except OSError:
                    return False
                if not data:
                    return False
                first = data.splitlines()[0].strip()
                if not first:
                    return False
                path = Path(first)
                self.save_document(path)
                if self._text_view:
                    self._text_view.grab_focus()
                return False
            if time.monotonic() - start_time > 300:
                self._update_status()
                return False
            return True

        GLib.timeout_add(200, _check)

    def _handle_normal_mode(self, key_name: str) -> bool:
        if key_name == "i":
            self.set_mode("insert")
            return True
        if key_name == ":":
            # Placeholder for command-line mode.
            return True
        return False

    def _handle_insert_mode(self, key_name: str) -> bool:
        if key_name == "Escape":
            self.set_mode("normal")
            return True
        if key_name in {"BackSpace", "Delete"}:
            return self._handle_inline_image_delete(key_name)
        return False

    def set_mode(self, mode: str) -> None:
        self._state.mode = mode
        self._update_status()

    def _update_status(self) -> None:
        if not self._status_label:
            return
        file_label = self._state.file_path.as_posix() if self._state.file_path else "[No File]"
        self._status_label.set_text(f"{self._state.mode.upper()}  {file_label}")

    def _set_status_hint(self, message: str) -> None:
        if not self._status_label:
            return
        self._status_label.set_text(message)

    def load_document(self, path: Path) -> None:
        self._state.file_path = path
        if not self._text_view:
            return
        if path.name.endswith(".gtkv.html"):
            self._load_gtkv_html(path)
            self.cleanup_cache()
        else:
            buffer = self._text_view.get_buffer()
            try:
                contents = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                contents = ""
            buffer.set_text(contents)
        self._update_status()

    def save_document(self, path: Optional[Path] = None) -> None:
        if not self._text_view:
            return
        target = path or self._state.file_path
        if not target:
            return
        target = self._ensure_gtkv_suffix(target, self._config.save_extension)
        html_text = self._build_gtkv_html()
        target.write_text(html_text, encoding="utf-8")
        self._state.file_path = target
        self._update_status()
        if self._status_label:
            self._status_label.set_text(f"SAVED  {target.as_posix()}")
        self.cleanup_cache()

    def insert_image(self, path: Path) -> None:
        """Insert an inline image node at the caret position."""
        if not self._text_view:
            return
        buffer = self._text_view.get_buffer()
        insert_iter = buffer.get_iter_at_mark(buffer.get_insert())
        anchor = self._insert_inline_image_at_iter(path, insert_iter)
        after_iter = insert_iter.copy()
        if after_iter.forward_char():
            buffer.place_cursor(after_iter)
        self._text_view.grab_focus()
        if anchor is not None:
            GLib.idle_add(self._load_inline_image, anchor, path)

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
        loading_label = Gtk.Label(label=f"Loading {path.name}…")
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
        self, path: Path, insert_iter: Gtk.TextIter
    ) -> Gtk.TextChildAnchor | None:
        if not self._text_view:
            return None
        buffer = self._text_view.get_buffer()
        anchor = buffer.create_child_anchor(insert_iter)
        widget = self._build_inline_image_widget(path)
        self._text_view.add_child_at_anchor(widget, anchor)
        self._inline_images[anchor] = InlineImageNode(path=path, status="loading", widget=widget)
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
        window_width = self._window.get_width() if self._window else 0
        if window_width and window_width > 200:
            max_width = max(320, min(1200, window_width - 120))
        else:
            max_width = 900
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(path.as_posix())
        if pixbuf.get_width() <= max_width:
            return pixbuf
        ratio = max_width / pixbuf.get_width()
        new_height = max(1, int(pixbuf.get_height() * ratio))
        return pixbuf.scale_simple(max_width, new_height, GdkPixbuf.InterpType.BILINEAR)

    def _handle_inline_image_delete(self, key_name: str) -> bool:
        if not self._text_view:
            return False
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

    def _remove_inline_anchor(self, anchor: Gtk.TextChildAnchor) -> None:
        node = self._inline_images.pop(anchor, None)
        if node and node.widget:
            node.widget.destroy()

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

    def _handle_save_request(self) -> None:
        target = self._state.file_path
        if target is None and self._config.file_selector.lower() == "o":
            if self._begin_save_selector_o():
                return
        if target is None:
            self._prompt_for_save_path()
            return
        if target is None:
            return
        try:
            self.save_document(target)
        except OSError:
            if self._status_label:
                self._status_label.set_text("SAVE FAILED")

    def _prompt_for_save_path(self) -> Path | None:
        default_name = "untitled"
        if self._config.save_extension:
            default_name = f"{default_name}.{self._config.save_extension}"
        dialog = Gtk.FileDialog()
        dialog.set_title("Save Document")
        dialog.set_modal(True)
        dialog.set_initial_name(default_name)

        def _on_saved(_dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
            try:
                file = _dialog.save_finish(result)
            except GLib.Error:
                return
            if not file:
                return
            path = file.get_path()
            if path:
                self.save_document(Path(path))

        dialog.save(self._window, None, _on_saved)
        return None

    def _begin_save_selector_o(self) -> bool:
        if shutil.which("o") is None:
            return False
        start_dir = Path.home()
        cache_path = self._get_o_picker_cache_path()
        if cache_path and cache_path.exists():
            try:
                cache_path.unlink()
            except OSError:
                pass
        cmd = ["o", "-s", start_dir.as_posix()]
        if self._config.save_extension:
            cmd.extend(["-lf", self._config.save_extension])
        self._set_status_hint("SAVE  Hit ENTER to select persistence dir")
        if not self._launch_terminal(cmd, cwd=start_dir):
            return False
        if not cache_path:
            return False
        self._poll_for_o_save_path(cache_path)
        return True

    @staticmethod
    def _ensure_gtkv_suffix(path: Path, extension: str | None) -> Path:
        if not extension:
            return path
        if path.name.endswith(f".{extension}"):
            return path
        if "." in path.name.lstrip("."):
            return path
        return Path(f"{path.as_posix()}.{extension}")

    def _build_gtkv_html(self) -> str:
        segments: list[tuple[str, str | tuple[str, str]]] = self._extract_document_segments()
        body_parts: list[str] = []
        for kind, payload in segments:
            if kind == "text":
                escaped = html.escape(cast(str, payload))
                body_parts.append(f"<pre class=\"text\">{escaped}</pre>")
            elif kind == "image":
                data_uri, alt = cast(tuple[str, str], payload)
                body_parts.append(
                    f"<img src=\"{data_uri}\" alt=\"{html.escape(alt)}\" />"
                )
        body = "\n".join(body_parts)
        return (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head>\n"
            "  <meta charset=\"utf-8\" />\n"
            "  <title>GTKV Document</title>\n"
            "  <style>body{font-family:monospace;white-space:normal;}"
            "pre.text{font-family:monospace;white-space:pre-wrap;}</style>\n"
            "</head>\n"
            "<body>\n"
            f"{body}\n"
            "</body>\n"
            "</html>\n"
        )

    def _extract_document_segments(self) -> list[tuple[str, str | tuple[str, str]]]:
        if not self._text_view:
            return []
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
        segments: list[tuple[str, str | tuple[str, str]]] = []
        current_iter = start_iter.copy()

        for offset, anchor in anchor_positions:
            anchor_iter = buffer.get_iter_at_offset(offset)
            if current_iter.get_offset() < anchor_iter.get_offset():
                text = buffer.get_text(current_iter, anchor_iter, True)
                if text:
                    segments.append(("text", text))
            node = self._inline_images.get(anchor)
            if node:
                data_uri = self._image_to_data_uri(node.path)
                if data_uri:
                    segments.append(("image", (data_uri, node.path.name)))
            current_iter = anchor_iter.copy()

        end_iter = buffer.get_end_iter()
        if current_iter.get_offset() < end_iter.get_offset():
            trailing = buffer.get_text(current_iter, end_iter, True)
            if trailing:
                segments.append(("text", trailing))

        if not segments:
            segments.append(("text", ""))
        return segments

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

    def _load_gtkv_html(self, path: Path) -> None:
        if not self._text_view:
            return
        buffer = self._text_view.get_buffer()
        buffer.set_text("")
        parser = _GTKVHTMLParser()
        try:
            contents = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            contents = ""
        parser.feed(contents)
        for token in parser.tokens:
            if token[0] == "text":
                buffer.insert(buffer.get_end_iter(), token[1])
            elif token[0] == "image":
                data_uri = token[1]
                image_path = self._materialize_data_uri(data_uri)
                if image_path:
                    anchor = self._insert_inline_image_at_iter(
                        image_path, buffer.get_end_iter()
                    )
                    if anchor is not None:
                        GLib.idle_add(self._load_inline_image, anchor, image_path)

    def _materialize_data_uri(self, data_uri: str) -> Path | None:
        if not data_uri.startswith("data:"):
            return None
        header, _, payload = data_uri.partition(",")
        if ";base64" not in header:
            return None
        mime = header[5:].split(";")[0] if header.startswith("data:") else ""
        ext = self._extension_for_mime(mime)
        try:
            data = base64.b64decode(payload)
        except (ValueError, OSError):
            return None
        digest = hashlib.sha1(data).hexdigest()
        cache_root = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        cache_dir = Path(cache_root) / "n" / "inline-images"
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None
        target = cache_dir / f"inline-{digest}.{ext}"
        if not target.exists():
            try:
                target.write_bytes(data)
            except OSError:
                return None
        else:
            try:
                os.utime(target, None)
            except OSError:
                pass
        return target

    def cleanup_cache(self) -> None:
        cache_root = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        cache_dir = Path(cache_root) / "n" / "inline-images"
        if not cache_dir.exists():
            return

        try:
            entries = [
                entry
                for entry in cache_dir.iterdir()
                if entry.is_file() and entry.name.startswith("inline-")
            ]
        except OSError:
            return

        now = time.time()
        max_age = self._config.cache_max_days * 86400
        max_bytes = self._config.cache_max_bytes
        max_files = self._config.cache_max_files

        def _stat(entry: Path) -> tuple[float, int]:
            try:
                stat = entry.stat()
                return stat.st_mtime, stat.st_size
            except OSError:
                return 0.0, 0

        for entry in entries:
            mtime, _size = _stat(entry)
            if max_age > 0 and now - mtime > max_age:
                try:
                    entry.unlink()
                except OSError:
                    pass

        try:
            entries = [
                entry
                for entry in cache_dir.iterdir()
                if entry.is_file() and entry.name.startswith("inline-")
            ]
        except OSError:
            return

        entries_with_stat: list[tuple[Path, float, int]] = []
        total_bytes = 0
        for entry in entries:
            mtime, size = _stat(entry)
            entries_with_stat.append((entry, mtime, size))
            total_bytes += size

        if (max_files and len(entries_with_stat) > max_files) or (
            max_bytes and total_bytes > max_bytes
        ):
            entries_with_stat.sort(key=lambda item: item[1])
            while entries_with_stat and (
                (max_files and len(entries_with_stat) > max_files)
                or (max_bytes and total_bytes > max_bytes)
            ):
                entry, _mtime, size = entries_with_stat.pop(0)
                try:
                    entry.unlink()
                except OSError:
                    pass
                total_bytes -= size

    def shutdown(self) -> None:
        """Shutdown hook for cleanup and persistence."""
        return

    @staticmethod
    def _extension_for_mime(mime: str) -> str:
        mapping = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/gif": "gif",
            "image/bmp": "bmp",
            "image/webp": "webp",
        }
        return mapping.get(mime, "png")


class _GTKVHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tokens: list[tuple[str, str]] = []
        self._in_pre = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "pre":
            self._in_pre = True
        if tag == "img":
            attrs_dict = {key: value for key, value in attrs}
            src = attrs_dict.get("src")
            if src:
                self.tokens.append(("image", src))

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre":
            self._in_pre = False

    def handle_data(self, data: str) -> None:
        if self._in_pre and data:
            self.tokens.append(("text", data))
