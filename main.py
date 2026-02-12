"""GTK application entry point."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Sequence

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from _version import __version__
from block_model import BlockDocument, ImageBlock, TextBlock, sample_document
from block_view import BlockEditorView
from persistence_sqlite import load_document, save_document


INSTALL_SH_URL = (
    "https://raw.githubusercontent.com/ryangerardwilson/gtkv/main/install.sh"
)
APP_ID = "com.gtkv.block"


class BlockApp(Gtk.Application):
    def __init__(self, image_path: str | None) -> None:
        super().__init__(application_id=APP_ID)
        self._image_path = image_path
        self._document: BlockDocument | None = None
        self._view: BlockEditorView | None = None
        self._last_picker_start = None
        self._last_doc_key = None
        self._active_editor: dict[str, object] | None = None

    def do_activate(self) -> None:
        window = Gtk.ApplicationWindow(application=self)
        window.set_title("GTKV")
        window.set_default_size(960, 720)

        if self._document is None:
            self._document = sample_document(self._image_path)
        self._view = BlockEditorView()
        self._view.set_document(self._document)

        controller = Gtk.EventControllerKey()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect("key-pressed", self._on_key_pressed)
        window.add_controller(controller)

        window.set_child(self._view)
        window.present()

    def _on_key_pressed(self, _controller, keyval, _keycode, state) -> bool:
        if self._document is None or self._view is None:
            return False

        return self._handle_doc_keys(keyval, state)

    def _handle_doc_keys(self, keyval, state) -> bool:
        if self._view is None or self._document is None:
            return False

        if state & Gdk.ModifierType.CONTROL_MASK:
            if keyval in (ord("v"), ord("V")):
                self._document.append_block(TextBlock("# New text block\n"))
                self._view.set_document(self._document)
                return True
            if keyval in (ord("i"), ord("I")):
                return self._begin_image_selector_o()
            if keyval in (ord("s"), ord("S")):
                return self._save_document()

        if keyval in (ord("j"), ord("J"), Gdk.KEY_Down):
            self._view.move_selection(1)
            self._last_doc_key = keyval
            return True

        if keyval in (ord("k"), ord("K"), Gdk.KEY_Up):
            self._view.move_selection(-1)
            self._last_doc_key = keyval
            return True

        if keyval in (ord("g"), ord("G")):
            if keyval == ord("G"):
                self._view.select_last()
                self._last_doc_key = None
                return True
            if self._last_doc_key == ord("g"):
                self._view.select_first()
                self._last_doc_key = None
                return True
            self._last_doc_key = ord("g")
            return True

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            return self._open_selected_text_block_editor()

        self._last_doc_key = None
        return False

    def _open_selected_text_block_editor(self) -> bool:
        if self._view is None or self._document is None:
            return False

        if self._active_editor is not None:
            return True

        if not self._view.selected_block_is_text():
            return True

        index = self._view.get_selected_index()
        block = self._document.blocks[index]
        if not isinstance(block, TextBlock):
            return True

        temp = tempfile.NamedTemporaryFile(
            prefix="gtkv-block-", suffix=".txt", delete=False
        )
        temp_path = Path(temp.name)
        temp.write(block.text.encode("utf-8"))
        temp.flush()
        temp.close()

        editor_cmd = self._pick_terminal_editor()
        if not editor_cmd:
            return True

        process = self._launch_terminal_process(editor_cmd + [temp_path.as_posix()])
        if not process:
            return True

        self._active_editor = {
            "process": process,
            "path": temp_path,
            "index": index,
        }

        GLib.timeout_add(250, self._poll_for_editor_exit)
        return True

    def _save_document(self) -> bool:
        if self._document is None:
            return False
        if self._document.path is not None:
            save_document(self._document.path, self._document)
            return True
        return self._begin_save_selector_o()

    def _poll_for_editor_exit(self) -> bool:
        if not self._active_editor or self._document is None or self._view is None:
            self._active_editor = None
            return False

        process = self._active_editor["process"]
        if isinstance(process, subprocess.Popen) and process.poll() is None:
            return True

        path = self._active_editor["path"]
        index = self._active_editor["index"]

        if isinstance(path, Path) and isinstance(index, int):
            try:
                updated_text = path.read_text(encoding="utf-8")
            except OSError:
                updated_text = None
            if updated_text is not None:
                self._document.set_text_block(index, updated_text)
                self._view.set_document(self._document)

            try:
                path.unlink()
            except OSError:
                pass

        self._active_editor = None
        return False

    def _begin_image_selector_o(self) -> bool:
        if self._document is None or self._view is None:
            return False

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

        if not self._launch_terminal(cmd, cwd=start_dir):
            return False

        if not cache_path:
            return False

        self._last_picker_start = time.monotonic()
        self._poll_for_o_picker_selection(cache_path)
        return True

    def _begin_save_selector_o(self) -> bool:
        if self._document is None:
            return False
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

        cmd = ["o", "-s", start_dir.as_posix()]
        if not self._launch_terminal(cmd, cwd=start_dir):
            return False

        if not cache_path:
            return False

        self._last_picker_start = time.monotonic()
        self._poll_for_o_save_path(cache_path)
        return True

    def _launch_terminal(self, command: list[str], cwd: Path | None = None) -> bool:
        return self._launch_terminal_process(command, cwd) is not None

    def _launch_terminal_process(
        self, command: list[str], cwd: Path | None = None
    ) -> subprocess.Popen | None:
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
            return process
        return None

    @staticmethod
    def _pick_terminal_editor() -> list[str] | None:
        for cmd in ("nvim", "vim", "vi"):
            path = shutil.which(cmd)
            if path:
                return [path]
        return None

    @staticmethod
    def _get_o_picker_cache_path() -> Path | None:
        cache_root = os.environ.get("XDG_CACHE_HOME")
        if cache_root:
            return Path(cache_root) / "o" / "picker-selection.txt"
        return Path.home() / ".cache" / "o" / "picker-selection.txt"

    def _poll_for_o_picker_selection(self, cache_path: Path) -> None:
        start_time = self._last_picker_start or time.monotonic()
        allowed_exts = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}

        def _check() -> bool:
            if self._document is None or self._view is None:
                return False
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
                        self._document.append_block(
                            ImageBlock(path.as_posix(), alt=path.name)
                        )
                        self._view.set_document(self._document)
                return False

            if time.monotonic() - start_time > 300:
                return False

            return True

        GLib.timeout_add(200, _check)

    def _poll_for_o_save_path(self, cache_path: Path) -> None:
        start_time = self._last_picker_start or time.monotonic()

        def _check() -> bool:
            if self._document is None:
                return False
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
                if path.suffix != ".docv":
                    path = path.with_suffix(".docv")
                save_document(path, self._document)
                return False

            if time.monotonic() - start_time > 300:
                return False

            return True

        GLib.timeout_add(200, _check)


def _load_css(css_path: Path) -> None:
    if not css_path.exists():
        return

    provider = Gtk.CssProvider()
    provider.load_from_path(str(css_path))
    display = Gdk.Display.get_default()
    if display is None:
        return

    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


def parse_args(argv: Sequence[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Block-based GTK4 editor with external Vim editing"
    )
    parser.add_argument("-v", "--version", action="store_true", help="Show version")
    parser.add_argument("-u", "--upgrade", action="store_true", help="Upgrade")
    parser.add_argument("--image", help="Optional image to show in sample doc")
    parser.add_argument("file", nargs="?", help="Optional .docv document to open")
    if hasattr(parser, "parse_known_intermixed_args"):
        args, gtk_args = parser.parse_known_intermixed_args(argv)
    else:
        args, gtk_args = parser.parse_known_args(argv)
    return args, gtk_args


def _run_upgrade() -> int:
    try:
        curl = subprocess.Popen(
            ["curl", "-fsSL", INSTALL_SH_URL],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        print("Upgrade requires curl", file=sys.stderr)
        return 1

    try:
        bash = subprocess.Popen(["bash", "-s", "--", "-u"], stdin=curl.stdout)
        if curl.stdout is not None:
            curl.stdout.close()
    except FileNotFoundError:
        print("Upgrade requires bash", file=sys.stderr)
        curl.terminate()
        curl.wait()
        return 1

    bash_rc = bash.wait()
    curl_rc = curl.wait()

    if curl_rc != 0:
        stderr = (
            curl.stderr.read().decode("utf-8", errors="replace") if curl.stderr else ""
        )
        if stderr:
            sys.stderr.write(stderr)
        return curl_rc

    return bash_rc


def _get_version() -> str:
    if __version__ and __version__ != "0.0.0":
        return __version__
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError:
        return __version__
    if result.returncode == 0:
        return result.stdout.strip() or __version__
    return __version__


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    options, gtk_args = parse_args(args)
    if options.version:
        print(_get_version())
        return 0
    if options.upgrade:
        return _run_upgrade()

    document_path = Path(options.file).expanduser() if options.file else None
    image_path = options.image or os.getenv("GTKV_IMAGE")
    if image_path and not os.path.exists(image_path):
        image_path = None

    if document_path and document_path.exists():
        app = BlockApp(None)
        app._document = load_document(document_path)
    else:
        app = BlockApp(image_path)
        if document_path:
            app._document = sample_document(image_path)
            app._document.set_path(document_path)
    _load_css(Path(__file__).with_name("style.css"))
    return app.run(gtk_args)


if __name__ == "__main__":
    raise SystemExit(main())
