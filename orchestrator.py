"""Application orchestrator coordinating UI, editor state, and image handling."""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # type: ignore

from config import AppConfig
from editor_command_controller import CommandController
from editor_command_parser import parse_ex_command
from editor_document import DocumentModel
from editor_mode_router import ModeRouter
from editor_segments import Segment
from editor_state import EditorState
from persistence_gtkv_html import build_html, parse_html
from services_image_cache import cleanup_cache as cleanup_image_cache
from logging_debug import log_action
from ui_status_controller import StatusController
from ui_window_shell import WindowShell


class Orchestrator:
    """Coordinates GTK widgets, editor state, and command handling."""

    def __init__(self, application: Gtk.Application, window: Gtk.ApplicationWindow, config: AppConfig) -> None:
        self._application = application
        self._window = window
        self._config = config
        self._state = EditorState()
        self._document = DocumentModel()
        self._mode_router = ModeRouter(
            self._state,
            on_mode_change=self.set_mode,
            on_inline_delete=self._handle_inline_image_delete,
            on_move=self._handle_move,
        )
        self._command_controller: Optional[CommandController] = None
        self._status_controller: Optional[StatusController] = None

        self._shell: Optional[WindowShell] = None

    def start(self) -> None:
        """Initialize UI, connect signals, and load initial document."""
        self._build_ui()
        self._connect_events()
        if self._config.startup_file:
            self.load_document(Path(self._config.startup_file))

    def _build_ui(self) -> None:
        self._shell = WindowShell(self._window, self._config)
        self._status_controller = StatusController(self._shell)
        self._status_controller.bind_state(self._state)
        self._command_controller = CommandController(
            pane=self._shell.command_pane,
            on_ex_command=self._handle_ex_command,
            on_search=self._handle_search_command,
            on_search_preview=self._handle_search_preview,
            on_status=self._set_status_hint,
            on_focus_editor=self._shell.editor_view.grab_focus,
        )
        self._command_controller.bind()
        self._shell.editor_view.set_document(self._document)
        self._shell.editor_view.set_editable(self._state.mode == "insert")
        self._shell.editor_view.set_cursor_mode(self._state.mode)

    def _connect_events(self) -> None:
        if not self._shell:
            return
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key_pressed)
        self._shell.editor_view.add_key_controller(controller)

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
        if self._state.mode == "normal" and self._is_colon_command(keyval, key_name, state):
            if self._command_controller:
                self._command_controller.show(":")
            return True
        if self._state.mode == "normal" and self._is_slash_command(keyval, key_name, state):
            if self._command_controller:
                self._command_controller.show("/")
            return True
        return self._mode_router.handle_key(key_name)

    def _is_ctrl_i(self, state: Gdk.ModifierType, key_name: str) -> bool:
        return key_name.lower() == "i" and bool(state & Gdk.ModifierType.CONTROL_MASK)

    def _is_ctrl_s(self, state: Gdk.ModifierType, key_name: str) -> bool:
        return key_name.lower() == "s" and bool(state & Gdk.ModifierType.CONTROL_MASK)

    def _is_colon_command(self, keyval: int, key_name: str, state: Gdk.ModifierType) -> bool:
        if key_name in {":", "colon"}:
            return True
        if keyval == Gdk.KEY_colon:
            return True
        if keyval == Gdk.KEY_semicolon and bool(state & Gdk.ModifierType.SHIFT_MASK):
            return True
        return False

    def _is_slash_command(self, keyval: int, key_name: str, state: Gdk.ModifierType) -> bool:
        if key_name in {"/", "slash"}:
            return True
        if keyval == Gdk.KEY_slash:
            return True
        if keyval == Gdk.KEY_question and bool(state & Gdk.ModifierType.SHIFT_MASK):
            return True
        return False

    def _open_image_chooser(self) -> None:
        log_action("open_image_chooser")
        if self._begin_image_selector_o():
            if self._shell:
                self._shell.editor_view.grab_focus()
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
                log_action(f"insert_image:{path}")
                self.insert_image(Path(path))
                if self._shell:
                    self._shell.editor_view.grab_focus()

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
                        log_action(f"insert_image:{path}")
                        self.insert_image(path)
                        if self._shell:
                            self._shell.editor_view.grab_focus()
                        if self._status_controller:
                            self._status_controller.refresh()
                return False
            if time.monotonic() - start_time > 300:
                if self._status_controller:
                    self._status_controller.refresh()
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
                log_action(f"save_document:{path}")
                self.save_document(path)
                if self._shell:
                    self._shell.editor_view.grab_focus()
                return False
            if time.monotonic() - start_time > 300:
                if self._status_controller:
                    self._status_controller.refresh()
                return False
            return True

        GLib.timeout_add(200, _check)

    def set_mode(self, mode: str) -> None:
        log_action(f"set_mode:{mode}")
        self._state.set_mode(mode)
        if not self._shell:
            return
        self._shell.editor_view.set_editable(mode == "insert")
        self._shell.editor_view.set_cursor_mode(mode)
        if mode == "visual":
            self._shell.editor_view.begin_visual_selection()
        else:
            self._shell.editor_view.clear_selection()
        if mode in {"normal", "visual"}:
            self._shell.editor_view.snap_cursor_to_line_start()

    def _handle_ex_command(self, text: str) -> bool:
        log_action(f"ex_command:{text}")
        command, _args = parse_ex_command(text)
        if not command:
            return True
        if command in {"w", "write"}:
            self._handle_save_request()
            return True
        if command in {"q", "quit"}:
            self._application.quit()
            return True
        if command in {"wq", "x"}:
            self._handle_save_request()
            self._application.quit()
            return True
        return False

    def _handle_search_command(self, text: str) -> bool:
        log_action(f"search_command:{text}")
        if not self._shell:
            return False
        term = text.strip()
        if not term:
            return True
        found = self._shell.editor_view.search_next(term)
        if not found:
            self._set_status_hint("NOT FOUND")
        return True

    def _handle_search_preview(self, text: str) -> bool:
        log_action(f"search_preview:{text}")
        if not self._shell:
            return False
        term = text.strip()
        if not term:
            return True
        return self._shell.editor_view.search_next(term)

    def _handle_move(self, direction: str, extend_selection: bool) -> bool:
        if not self._shell:
            return False
        return self._shell.editor_view.move_cursor(direction, extend_selection)

    def _set_status_hint(self, message: str) -> None:
        if not self._status_controller:
            return
        self._status_controller.set_hint(message)

    def load_document(self, path: Path) -> None:
        log_action(f"load_document:{path}")
        self._state.set_file_path(path)
        if not self._shell:
            return
        if path.name.endswith(".gtkv.html"):
            self._load_gtkv_html(path)
            self.cleanup_cache()
        else:
            try:
                contents = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                contents = ""
            self._document.set_text(contents)

    def save_document(self, path: Optional[Path] = None) -> None:
        if not self._shell:
            return
        target = path or self._state.file_path
        if not target:
            return
        log_action(f"save_document:{target}")
        self._document.set_segments(self._shell.editor_view.extract_segments())
        target = self._ensure_gtkv_suffix(target, self._config.save_extension)
        html_text = self._build_gtkv_html()
        target.write_text(html_text, encoding="utf-8")
        self._state.set_file_path(target)
        if self._status_controller:
            self._status_controller.set_status_text(f"SAVED  {target.as_posix()}")
        self.cleanup_cache()

    def insert_image(self, path: Path) -> None:
        """Insert an inline image node at the caret position."""
        if not self._shell:
            return
        log_action(f"insert_image:{path}")
        self._shell.editor_view.insert_image(path)

    def _handle_inline_image_delete(self, key_name: str) -> bool:
        if not self._shell:
            return False
        log_action(f"inline_image_delete:{key_name}")
        return self._shell.editor_view.handle_inline_image_delete(key_name)

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
            if self._status_controller:
                self._status_controller.set_status_text("SAVE FAILED")

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
        return self._document.get_segments()

    def _load_gtkv_html(self, path: Path) -> None:
        if not self._shell:
            return
        try:
            contents = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            contents = ""
        segments = parse_html(contents)
        self._document.set_segments(segments)

    def cleanup_cache(self) -> None:
        cleanup_image_cache(
            max_days=self._config.cache_max_days,
            max_bytes=self._config.cache_max_bytes,
            max_files=self._config.cache_max_files,
        )

    def shutdown(self) -> None:
        """Shutdown hook for cleanup and persistence."""
        return
