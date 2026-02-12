from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from block_model import BlockDocument, ImageBlock, TextBlock, sample_document
from block_view import BlockEditorView


APP_ID = "com.gtkv.BlockPrototype"


class BlockPrototypeApp(Gtk.Application):
    def __init__(self, image_path: str | None) -> None:
        super().__init__(application_id=APP_ID)
        self._image_path = image_path
        self._document: BlockDocument | None = None
        self._view: BlockEditorView | None = None
        self._last_picker_start = None
        self._mode = "doc"
        self._last_doc_key = None

    def do_activate(self) -> None:
        window = Gtk.ApplicationWindow(application=self)
        window.set_title("GTKV Block Prototype")
        window.set_default_size(960, 720)

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

        if self._mode == "doc":
            return self._handle_doc_keys(keyval, state)

        if keyval == Gdk.KEY_Escape:
            self._mode = "doc"
            self._view.refresh_selection()
            self._view.grab_focus()
            return True

        return False

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
            if self._view.focus_selected_block():
                self._mode = "block"
                self._view.clear_selection()
            return True

        self._last_doc_key = None
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
                subprocess.Popen(
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GTKV block prototype")
    parser.add_argument("--image", help="Path to an image to render")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    image_path = args.image or os.getenv("GTKV_PROTO_IMAGE")
    if image_path and not os.path.exists(image_path):
        image_path = None

    app = BlockPrototypeApp(image_path)
    _load_css(Path(__file__).with_name("style.css"))
    app.run([])


if __name__ == "__main__":
    main()
