"""Application orchestration and GTK setup."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk  # type: ignore[attr-defined]

import actions
import config
import document_io
import editor
import picker
import py_runner
from _version import __version__
from app_state import AppState
from block_model import PythonImageBlock, sample_document
from block_view import BlockEditorView


INSTALL_SH_URL = (
    "https://raw.githubusercontent.com/ryangerardwilson/gtkv/main/install.sh"
)
APP_ID = "com.gtkv.block"


class BlockApp(Gtk.Application):
    def __init__(self, orchestrator: "Orchestrator") -> None:
        super().__init__(application_id=APP_ID)
        self._orchestrator = orchestrator

    def do_activate(self) -> None:
        window = Gtk.ApplicationWindow(application=self)
        self._orchestrator.configure_window(window)


class Orchestrator:
    def __init__(self) -> None:
        self._state = AppState()
        self._image_path: str | None = None
        self._python_path: str | None = None

    def run(self, argv: Sequence[str] | None = None) -> int:
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
        self._image_path = image_path
        self._python_path = config.get_python_path()
        if not self._python_path:
            self._python_path = _prompt_python_path_cli()
            if self._python_path:
                config.set_python_path(self._python_path)

        if document_path and document_path.exists():
            self._state.document = document_io.load(document_path)
        elif document_path:
            self._state.document = sample_document(image_path)
            self._state.document.set_path(document_path)

        app = BlockApp(self)
        _load_css(Path(__file__).with_name("style.css"))
        return app.run(gtk_args)

    def configure_window(self, window: Gtk.ApplicationWindow) -> None:
        window.set_title("GTKV")
        window.set_default_size(960, 720)

        document = self._state.document
        if document is None:
            document = sample_document(self._image_path)
            self._state.document = document

        view: BlockEditorView = BlockEditorView()
        view.set_document(document)
        self._state.view = view
        self._render_python_images_on_start()

        controller = Gtk.EventControllerKey()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect("key-pressed", self.on_key_pressed)
        window.add_controller(controller)

        window.set_child(view)
        window.present()

    def on_key_pressed(self, _controller, keyval, _keycode, state) -> bool:
        if self._state.document is None or self._state.view is None:
            return False

        return self._handle_doc_keys(keyval, state)

    def _handle_doc_keys(self, keyval, state) -> bool:
        if state & Gdk.ModifierType.CONTROL_MASK:
            if keyval in (ord("v"), ord("V")):
                return actions.insert_text_block(self._state)
            if keyval in (ord("i"), ord("I")):
                return self._begin_image_selector_o()
            if keyval == ord("3"):
                return self._insert_three_block()
            if keyval in (ord("p"), ord("P")):
                return self._insert_python_image_block()
            if keyval in (ord("l"), ord("L")):
                return self._insert_latex_block()
            if keyval in (ord("s"), ord("S")):
                return self._save_document()

        if keyval in (ord("j"), ord("J"), Gdk.KEY_Down):
            actions.move_selection(self._state, 1)
            self._state.last_doc_key = keyval
            return True

        if keyval in (ord("k"), ord("K"), Gdk.KEY_Up):
            actions.move_selection(self._state, -1)
            self._state.last_doc_key = keyval
            return True

        if keyval in (ord("g"), ord("G")):
            if keyval == ord("G"):
                actions.select_last(self._state)
                self._state.last_doc_key = None
                return True
            if self._state.last_doc_key == ord("g"):
                actions.select_first(self._state)
                self._state.last_doc_key = None
                return True
            self._state.last_doc_key = ord("g")
            return True

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            return self._open_selected_block_editor()

        self._state.last_doc_key = None
        return False

    def _open_selected_block_editor(self) -> bool:
        if self._state.active_editor is not None:
            return True

        payload = actions.get_selected_edit_payload(self._state)
        if payload is None:
            return True

        index, content, suffix, kind = payload
        session = editor.open_temp_editor(content, suffix, index, kind)
        if session is None:
            return True

        self._state.active_editor = session
        editor.schedule_editor_poll(session, self._handle_editor_update, self._clear_editor)
        return True

    def _handle_editor_update(self, index: int, kind: str, updated_text: str) -> None:
        actions.update_block_from_editor(self._state, index, kind, updated_text)
        if kind == "pyimage":
            self._render_python_image(index)

    def _clear_editor(self) -> None:
        self._state.active_editor = None

    def _insert_three_block(self) -> bool:
        if not actions.insert_three_block(self._state):
            return False
        return self._open_selected_block_editor()

    def _insert_python_image_block(self) -> bool:
        if not actions.insert_python_image_block(self._state):
            return False
        return self._open_selected_block_editor()

    def _insert_latex_block(self) -> bool:
        if not actions.insert_latex_block(self._state):
            return False
        return self._open_selected_block_editor()

    def _save_document(self) -> bool:
        document = self._state.document
        if document is None:
            return False
        if document.path is not None:
            document_io.save(document.path, document)
            return True
        return self._begin_save_selector_o()

    def _begin_image_selector_o(self) -> bool:
        if self._state.document is None or self._state.view is None:
            return False

        start_dir = _get_picker_start_dir()

        def _on_pick(path: Path) -> None:
            actions.insert_image_block(self._state, path)

        return picker.begin_image_selector_o(start_dir, _on_pick)

    def _begin_save_selector_o(self) -> bool:
        document = self._state.document
        if document is None:
            return False

        start_dir = _get_picker_start_dir()

        def _on_pick(path: Path) -> None:
            document_io.save(path, document)

        return picker.begin_save_selector_o(start_dir, _on_pick)

    def _render_python_image(self, index: int) -> None:
        document = self._state.document
        view = self._state.view
        if document is None or view is None:
            return

        if index < 0 or index >= len(document.blocks):
            return
        block = document.blocks[index]
        if not isinstance(block, PythonImageBlock):
            return

        python_path = self._python_path
        if not python_path:
            document.set_python_image_render(
                index,
                rendered_data=None,
                rendered_hash=None,
                last_error="Python path not configured",
                rendered_path=None,
            )
            view.set_document(document)
            return

        result = py_runner.render_python_image(block.source, python_path, block.format)
        document.set_python_image_render(
            index,
            rendered_data=result.rendered_data,
            rendered_hash=result.rendered_hash,
            last_error=result.error,
            rendered_path=None,
        )
        view.set_document(document)

    def _render_python_images_on_start(self) -> None:
        document = self._state.document
        if document is None:
            return
        for index, block in enumerate(document.blocks):
            if isinstance(block, PythonImageBlock):
                self._render_python_image(index)

def _get_picker_start_dir() -> Path:
    downloads_dir = Path.home() / "Downloads"
    if downloads_dir.exists():
        return downloads_dir
    return Path.home()


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


def _prompt_python_path_cli() -> str | None:
    try:
        text = input("Python path for rendering (leave blank to skip): ").strip()
    except EOFError:
        return None
    if not text:
        return None
    if not os.path.exists(text):
        return None
    if not os.access(text, os.X_OK):
        return None
    return text


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
