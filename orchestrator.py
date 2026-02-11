"""Application orchestrator coordinating UI, editor state, and image handling."""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, cast

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # type: ignore

from config import AppConfig
from editor_mode_router import ModeRouter
from editor_segments import Segment
from editor_state import EditorState
from persistence_gtkv_html import build_html, parse_html
from services_image_cache import cleanup_cache as cleanup_image_cache
from ui_editor_view import EditorView


class Orchestrator:
    """Coordinates GTK widgets, editor state, and command handling."""

    def __init__(self, application: Gtk.Application, window: Gtk.ApplicationWindow, config: AppConfig) -> None:
        self._application = application
        self._window = window
        self._config = config
        self._state = EditorState()
        self._mode_router = ModeRouter(
            self._state,
            on_mode_change=self.set_mode,
            on_inline_delete=self._handle_inline_image_delete,
        )

        self._root: Optional[Gtk.Box] = None
        self._status_label: Optional[Gtk.Label] = None
        self._editor_view: Optional[EditorView] = None

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

        editor_view = EditorView(self._window)
        self._editor_view = editor_view
        root.append(editor_view.widget)

        status_label = cast(Gtk.Label, Gtk.Label(label=""))
        status_label.set_xalign(0.0)
        self._status_label = status_label
        root.append(status_label)

    def _connect_events(self) -> None:
        if not self._editor_view:
            return
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key_pressed)
        self._editor_view.add_key_controller(controller)

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
        return self._mode_router.handle_key(key_name)

    def _is_ctrl_i(self, state: Gdk.ModifierType, key_name: str) -> bool:
        return key_name.lower() == "i" and bool(state & Gdk.ModifierType.CONTROL_MASK)

    def _is_ctrl_s(self, state: Gdk.ModifierType, key_name: str) -> bool:
        return key_name.lower() == "s" and bool(state & Gdk.ModifierType.CONTROL_MASK)

    def _open_image_chooser(self) -> None:
        if self._begin_image_selector_o():
            if self._editor_view:
                self._editor_view.grab_focus()
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
                if self._editor_view:
                    self._editor_view.grab_focus()

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
                        if self._editor_view:
                            self._editor_view.grab_focus()
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
                if self._editor_view:
                    self._editor_view.grab_focus()
                return False
            if time.monotonic() - start_time > 300:
                self._update_status()
                return False
            return True

        GLib.timeout_add(200, _check)

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
        if not self._editor_view:
            return
        if path.name.endswith(".gtkv.html"):
            self._load_gtkv_html(path)
            self.cleanup_cache()
        else:
            try:
                contents = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                contents = ""
            self._editor_view.set_text(contents)
        self._update_status()

    def save_document(self, path: Optional[Path] = None) -> None:
        if not self._editor_view:
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
        if not self._editor_view:
            return
        self._editor_view.insert_image(path)

    def _handle_inline_image_delete(self, key_name: str) -> bool:
        if not self._editor_view:
            return False
        return self._editor_view.handle_inline_image_delete(key_name)

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
        if target is None and self._begin_save_selector_o():
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
        segments = self._extract_document_segments()
        return build_html(segments)

    def _extract_document_segments(self) -> list[Segment]:
        if not self._editor_view:
            return []
        return self._editor_view.extract_segments()

    def _load_gtkv_html(self, path: Path) -> None:
        if not self._editor_view:
            return
        try:
            contents = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            contents = ""
        segments = parse_html(contents)
        self._editor_view.load_segments(segments)

    def cleanup_cache(self) -> None:
        cleanup_image_cache(
            max_days=self._config.cache_max_days,
            max_bytes=self._config.cache_max_bytes,
            max_files=self._config.cache_max_files,
        )

    def shutdown(self) -> None:
        """Shutdown hook for cleanup and persistence."""
        return
