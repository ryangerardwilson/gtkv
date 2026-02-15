"""Application orchestration and GTK setup."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk  # type: ignore[import-not-found, attr-defined]

import actions
import config
import document_io
import editor
import py_runner
from export_html import export_document
from design_constants import colors_for, font
from _version import __version__
from app_state import AppState
from block_model import (
    BlockDocument,
    MapBlock,
    PythonImageBlock,
    TextBlock,
    sample_document,
)
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
        self._python_path: str | None = None
        self._ui_mode: str | None = None
        self._mode = "document"
        self._open_vault_on_start = False
        self._leader_active = False
        self._leader_buffer = ""
        self._leader_start = 0.0
        self._delete_pending = False
        self._delete_start = 0.0
        self._yank_pending = False
        self._yank_start = 0.0
        self._demo = False

    def run(self, argv: Sequence[str] | None = None) -> int:
        args = list(sys.argv[1:] if argv is None else argv)
        options, gtk_args, parser = parse_args(args)
        if options.version:
            print(_get_version())
            return 0
        if options.upgrade:
            return _run_upgrade()
        if options.file == "init":
            return _run_init()
        if options.export:
            return _run_export(options.export, options.file)

        self._demo = options.demo

        document_path = Path(options.file).expanduser() if options.file else None
        self._python_path = config.get_python_path()
        if not self._python_path:
            self._python_path = _prompt_python_path_cli()
            if self._python_path:
                config.set_python_path(self._python_path)

        self._ui_mode = config.get_ui_mode()
        if not self._ui_mode:
            self._ui_mode = _prompt_ui_mode_cli()
            if self._ui_mode:
                config.set_ui_mode(self._ui_mode)

        if document_path is not None and document_path.exists():
            self._state.document = document_io.load(document_path)
        else:
            if self._demo:
                self._state.document = sample_document()
            else:
                self._state.document = BlockDocument([])
            if document_path is not None:
                self._state.document.set_path(document_path)
            if document_path is None and not self._demo:
                vaults = [path for path in config.get_vaults() if path.exists()]
                if vaults:
                    project_root = _find_project_root()
                    if project_root is not None:
                        root_in_vaults = project_root in vaults
                    else:
                        root_in_vaults = False
                    if project_root is not None and root_in_vaults:
                        if _vault_has_docs(project_root):
                            self._open_vault_on_start = True
                    elif not any(_vault_has_docs(path) for path in vaults):
                        self._open_vault_on_start = True

        app = BlockApp(self)
        _load_css(Path(__file__).with_name("style.css"), self._ui_mode or "dark")
        return app.run(gtk_args)

    def configure_window(self, window: Gtk.ApplicationWindow) -> None:
        window.set_title("GTKV")
        window.set_default_size(960, 720)

        document = self._state.document
        if document is None:
            document = BlockDocument([])
            self._state.document = document

        view: BlockEditorView = BlockEditorView(self._ui_mode or "dark")
        view.set_document(document)
        self._state.view = view
        self._render_python_images_on_start()
        if self._open_vault_on_start:
            self._open_vault_on_start = False
            self._open_vault_mode()

        controller = Gtk.EventControllerKey()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect("key-pressed", self.on_key_pressed)
        window.add_controller(controller)

        window.set_child(view)
        window.present()

    def on_key_pressed(self, _controller, keyval, _keycode, state) -> bool:
        if self._state.document is None or self._state.view is None:
            return False

        if self._mode == "vault":
            action = self._state.view.handle_vault_key(keyval)
            if action.opened_path is not None:
                self._open_document_path(action.opened_path)
                self._close_vault_mode()
            elif action.close:
                self._close_vault_mode()
            return action.handled

        return self._handle_doc_keys(keyval, state)

    def _handle_doc_keys(self, keyval, state) -> bool:
        if self._state.view is not None and self._state.view.toc_drill_active():
            return self._state.view.handle_toc_drill_key(keyval)
        if self._leader_active:
            if self._handle_leader_keys(keyval, state):
                return True
        if self._handle_delete_keys(keyval, state):
            return True
        if self._handle_yank_keys(keyval, state):
            return True
        if self._handle_leader_keys(keyval, state):
            return True
        if keyval in (ord("?"), Gdk.KEY_question):
            if self._state.view is not None:
                self._state.view.toggle_help()
            return True
        if state & Gdk.ModifierType.CONTROL_MASK:
            if keyval in (ord("s"), ord("S")):
                if self._save_document():
                    self._show_status("Saved", "success")
                else:
                    self._show_status("Save failed", "error")
                return True
            if keyval in (ord("e"), ord("E")):
                if self._export_current_html():
                    self._show_status("Exported HTML", "success")
                else:
                    self._show_status("Export failed", "error")
                return True
            if keyval in (ord("t"), ord("T")):
                if self._save_document():
                    self._show_status("Saved", "success")
                    self._quit()
                    return True
                self._show_status("Save failed", "error")
                return True
            if keyval in (ord("x"), ord("X")):
                self._quit()
                return True
            if keyval in (ord("j"), ord("J")):
                return actions.move_block(self._state, 1)
            if keyval in (ord("k"), ord("K")):
                return actions.move_block(self._state, -1)

        if keyval in (ord("p"), ord("P")):
            if self._state.clipboard_block is None:
                self._show_status("Nothing to paste", "error")
                return True
            if actions.paste_after_selected(self._state, self._state.clipboard_block):
                self._show_status("Pasted block", "success")
            else:
                self._show_status("Paste failed", "error")
            return True

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

        if keyval in (ord("q"), ord("Q")):
            self._quit()
            return True

        self._state.last_doc_key = None
        return False

    def _handle_delete_keys(self, keyval, state) -> bool:
        if state & Gdk.ModifierType.CONTROL_MASK:
            if self._delete_pending:
                self._delete_pending = False
            return False

        now = time.monotonic()
        if self._delete_pending and now - self._delete_start > 1.25:
            self._delete_pending = False

        if keyval in (ord("d"), ord("D")):
            if not self._delete_pending:
                self._delete_pending = True
                self._delete_start = now
                return True
            self._delete_pending = False
            deleted = actions.delete_selected_block(self._state)
            if deleted is None:
                self._show_status("Nothing to delete", "error")
                return True
            self._state.clipboard_block = deleted
            self._show_status("Deleted block", "success")
            return True

        if self._delete_pending:
            self._delete_pending = False
        return False

    def _handle_yank_keys(self, keyval, state) -> bool:
        if state & Gdk.ModifierType.CONTROL_MASK:
            if self._yank_pending:
                self._yank_pending = False
            return False

        now = time.monotonic()
        if self._yank_pending and now - self._yank_start > 1.25:
            self._yank_pending = False

        if keyval in (ord("y"), ord("Y")):
            if not self._yank_pending:
                self._yank_pending = True
                self._yank_start = now
                return True
            self._yank_pending = False
            yanked = actions.yank_selected_block(self._state)
            if yanked is None:
                self._show_status("Nothing to yank", "error")
                return True
            self._state.clipboard_block = yanked
            self._show_status("Yanked block", "success")
            return True

        if self._yank_pending:
            self._yank_pending = False
        return False

    def _handle_leader_keys(self, keyval, state) -> bool:
        if state & Gdk.ModifierType.CONTROL_MASK:
            return False
        if keyval == ord(",") and not self._leader_active:
            self._leader_active = True
            self._leader_buffer = ""
            self._leader_start = time.monotonic()
            return True
        if not self._leader_active:
            return False
        if time.monotonic() - self._leader_start > 2.0:
            self._leader_active = False
            self._leader_buffer = ""
            return False
        if keyval == Gdk.KEY_Escape:
            self._leader_active = False
            self._leader_buffer = ""
            return True
        if 32 <= keyval <= 126:
            self._leader_buffer += chr(keyval)
        else:
            return True

        if self._leader_buffer == "j":
            self._leader_active = False
            return actions.select_last(self._state)
        if self._leader_buffer == "k":
            self._leader_active = False
            return actions.select_first(self._state)
        if self._leader_buffer == "bjs":
            self._leader_active = False
            return self._insert_three_block()
        if self._leader_buffer == "bpy":
            self._leader_active = False
            return self._insert_python_image_block()
        if self._leader_buffer == "bltx":
            self._leader_active = False
            return self._insert_latex_block()
        if self._leader_buffer == "bmap":
            self._leader_active = False
            return self._insert_map_block()
        if self._leader_buffer == "bht":
            self._leader_active = False
            return actions.insert_text_block(self._state, kind="title")
        if self._leader_buffer == "bh1":
            self._leader_active = False
            return actions.insert_text_block(self._state, kind="h1")
        if self._leader_buffer == "bh2":
            self._leader_active = False
            return actions.insert_text_block(self._state, kind="h2")
        if self._leader_buffer == "bh3":
            self._leader_active = False
            return actions.insert_text_block(self._state, kind="h3")
        if self._leader_buffer == "bn":
            self._leader_active = False
            return actions.insert_text_block(self._state, kind="body")
        if self._leader_buffer == "bi":
            self._leader_active = False
            return actions.insert_toc_block(self._state)
        if self._leader_buffer == "i":
            self._leader_active = False
            if self._state.document is None or self._state.view is None:
                return False
            toc_exists = any(
                isinstance(block, TextBlock) and block.kind == "toc"
                for block in self._state.document.blocks
            )
            if not toc_exists:
                insert_at = self._state.view.get_selected_index()
                self._state.document.insert_block_after(
                    insert_at, TextBlock("", kind="toc")
                )
                self._state.view.set_document(self._state.document)
            self._state.view.open_toc_drill(self._state.document)
            return True
        if self._leader_buffer == "m":
            self._leader_active = False
            self._toggle_ui_mode()
            return True
        if self._leader_buffer == "v":
            self._leader_active = False
            return self._open_vault_mode()
        return True

    def _quit(self) -> None:
        app = Gtk.Application.get_default()
        if app is not None:
            app.quit()
        else:
            raise SystemExit(0)

    def _show_status(self, message: str, kind: str = "info") -> None:
        if self._state.view is not None:
            self._state.view.show_status(message, kind)

    def _toggle_ui_mode(self) -> None:
        current = (self._ui_mode or "dark").lower()
        next_mode = "light" if current == "dark" else "dark"
        self._ui_mode = next_mode
        config.set_ui_mode(next_mode)
        _load_css(Path(__file__).with_name("style.css"), next_mode)
        if self._state.document is not None and self._state.view is not None:
            self._state.view.set_ui_mode(next_mode, self._state.document)
            self._rerender_map_blocks()
        self._show_status(f"Theme: {next_mode}", "success")

    def _open_document_path(self, document_path: Path) -> None:
        if not document_path.exists():
            self._show_status("Missing document", "error")
            return
        try:
            self._state.document = document_io.load(document_path)
        except OSError:
            self._show_status("Failed to load document", "error")
            return
        if self._state.view is not None and self._state.document is not None:
            self._state.view.set_document(self._state.document)
        self._render_python_images_on_start()

    def _open_vault_mode(self) -> bool:
        if self._state.active_editor is not None:
            self._show_status("Close editor first", "error")
            return True
        if self._state.view is None:
            return False
        vaults = [path for path in config.get_vaults() if path.exists()]
        if not vaults:
            self._show_status("No vaults registered", "error")
            return True
        self._mode = "vault"
        self._state.view.open_vault_mode(vaults)
        return True

    def _close_vault_mode(self) -> None:
        if self._state.view is None:
            return
        self._mode = "document"
        self._state.view.close_vault_mode()

    def _rerender_map_blocks(self) -> None:
        document = self._state.document
        view = self._state.view
        if document is None or view is None:
            return
        for index, block in enumerate(document.blocks):
            if isinstance(block, MapBlock):
                view.reload_media_at(index)

    def _open_selected_block_editor(self) -> bool:
        if self._state.active_editor is not None:
            return True

        if self._state.document is not None and self._state.view is not None:
            index = self._state.view.get_selected_index()
            try:
                block = self._state.document.blocks[index]
            except IndexError:
                block = None
            if isinstance(block, TextBlock) and block.kind == "toc":
                self._state.view.open_toc_drill(self._state.document)
                return True

        payload = actions.get_selected_edit_payload(self._state)
        if payload is None:
            return True

        index, content, suffix, kind = payload
        session = editor.open_temp_editor(content, suffix, index, kind)
        if session is None:
            return True

        self._state.active_editor = session
        editor.schedule_editor_poll(
            session, self._handle_editor_update, self._clear_editor
        )
        return True

    def _handle_editor_update(self, index: int, kind: str, updated_text: str) -> None:
        actions.update_block_from_editor(self._state, index, kind, updated_text)
        if kind == "pyimage":
            self._render_python_image(index)
            return
        view = self._state.view
        if view is None:
            return
        if kind == "text":
            view.update_text_at(index, updated_text)
            return
        view.reload_media_at(index)

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

    def _insert_map_block(self) -> bool:
        if not actions.insert_map_block(self._state):
            return False
        return self._open_selected_block_editor()

    def _save_document(self) -> bool:
        document = self._state.document
        if document is None:
            return False
        if document.path is not None:
            document_io.save(document.path, document)
            return True
        print("No document path set; launch with a .docv filename", file=sys.stderr)
        return False

    def _export_current_html(self) -> bool:
        document = self._state.document
        if document is None or document.path is None:
            print("No document path set; cannot export", file=sys.stderr)
            return False
        output_path = document.path.with_suffix(".html")
        export_document(
            document, output_path, self._python_path, self._ui_mode or "dark"
        )
        return True

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
                rendered_data_dark=None,
                rendered_hash_dark=None,
                rendered_data_light=None,
                rendered_hash_light=None,
                last_error="Python path not configured",
            )
            view.set_document(document)
            return

        dark = py_runner.render_python_image(
            block.source, python_path, block.format, ui_mode="dark"
        )
        light = py_runner.render_python_image(
            block.source, python_path, block.format, ui_mode="light"
        )
        error = dark.error or light.error
        document.set_python_image_render(
            index,
            rendered_data_dark=dark.rendered_data,
            rendered_hash_dark=dark.rendered_hash,
            rendered_data_light=light.rendered_data,
            rendered_hash_light=light.rendered_hash,
            last_error=error,
        )
        view.set_document(document)

    def _render_python_images_on_start(self) -> None:
        document = self._state.document
        if document is None:
            return
        for index, block in enumerate(document.blocks):
            if isinstance(block, PythonImageBlock):
                self._render_python_image(index)


def _load_css(css_path: Path, ui_mode: str) -> None:
    if not css_path.exists():
        return

    palette = colors_for(ui_mode)
    variables = ":root {\n"
    variables += f"  --block-text-color: {palette.block_text};\n"
    variables += f"  --block-text-size: {font.block_text};\n"
    variables += f"  --block-title-color: {palette.block_title};\n"
    variables += f"  --block-title-size: {font.block_title};\n"
    variables += f"  --block-h1-color: {palette.block_h1};\n"
    variables += f"  --block-h1-size: {font.block_h1};\n"
    variables += f"  --block-h2-color: {palette.block_h2};\n"
    variables += f"  --block-h2-size: {font.block_h2};\n"
    variables += f"  --block-h3-color: {palette.block_h3};\n"
    variables += f"  --block-h3-size: {font.block_h3};\n"
    variables += f"  --block-toc-color: {palette.block_toc};\n"
    variables += f"  --block-toc-size: {font.block_toc};\n"
    variables += f"  --app-background: {palette.app_background};\n"
    variables += f"  --block-image-label-color: {palette.block_image_label};\n"
    variables += f"  --block-selected-shadow: {palette.block_selected_shadow};\n"
    variables += (
        f"  --block-selected-background: {palette.block_selected_background};\n"
    )
    variables += f"  --help-panel-background: {palette.help_panel_background};\n"
    variables += f"  --help-panel-border: {palette.help_panel_border};\n"
    variables += f"  --help-title-color: {palette.help_title};\n"
    variables += f"  --help-title-size: {font.help_title};\n"
    variables += f"  --help-body-color: {palette.help_body};\n"
    variables += f"  --help-body-size: {font.help_body};\n"
    variables += f"  --toc-panel-background: {palette.toc_panel_background};\n"
    variables += f"  --toc-panel-border: {palette.toc_panel_border};\n"
    variables += f"  --toc-panel-shadow: {palette.toc_panel_shadow};\n"
    variables += f"  --toc-title-color: {palette.toc_title};\n"
    variables += f"  --toc-title-size: {font.toc_title};\n"
    variables += f"  --toc-hint-color: {palette.toc_hint};\n"
    variables += f"  --toc-hint-size: {font.toc_hint};\n"
    variables += (
        f"  --toc-row-selected-background: {palette.toc_row_selected_background};\n"
    )
    variables += f"  --toc-row-selected-border: {palette.toc_row_selected_border};\n"
    variables += f"  --toc-row-label-color: {palette.toc_row_label};\n"
    variables += f"  --toc-row-size: {font.toc_row};\n"
    variables += f"  --toc-empty-color: {palette.toc_empty};\n"
    variables += f"  --toc-empty-size: {font.toc_empty};\n"
    variables += f"  --vault-panel-background: {palette.vault_panel_background};\n"
    variables += f"  --vault-panel-border: {palette.vault_panel_border};\n"
    variables += f"  --vault-panel-shadow: {palette.vault_panel_shadow};\n"
    variables += f"  --vault-title-color: {palette.vault_title};\n"
    variables += f"  --vault-title-size: {font.vault_title};\n"
    variables += f"  --vault-subtitle-color: {palette.vault_subtitle};\n"
    variables += f"  --vault-subtitle-size: {font.vault_subtitle};\n"
    variables += f"  --vault-hint-color: {palette.vault_hint};\n"
    variables += f"  --vault-hint-size: {font.vault_hint};\n"
    variables += (
        f"  --vault-row-selected-background: {palette.vault_row_selected_background};\n"
    )
    variables += f"  --vault-row-selected-border: {palette.vault_row_selected_border};\n"
    variables += f"  --vault-row-label-color: {palette.vault_row_label};\n"
    variables += f"  --vault-row-size: {font.vault_row};\n"
    variables += f"  --vault-empty-color: {palette.vault_empty};\n"
    variables += f"  --vault-empty-size: {font.vault_empty};\n"
    variables += f"  --status-background: {palette.status_background};\n"
    variables += f"  --status-border: {palette.status_border};\n"
    variables += f"  --status-text-color: {palette.status_text};\n"
    variables += f"  --status-size: {font.status};\n"
    variables += f"  --status-success-color: {palette.status_success};\n"
    variables += f"  --status-error-color: {palette.status_error};\n"
    variables += "}\n"

    provider = Gtk.CssProvider()
    provider.load_from_data(variables.encode("utf-8"))
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

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


def _prompt_ui_mode_cli() -> str | None:
    try:
        text = input("UI mode (dark/light, leave blank for dark): ").strip().lower()
    except EOFError:
        return None
    if not text:
        return "dark"
    if text in {"dark", "light"}:
        return text
    return None


def parse_args(
    argv: Sequence[str],
) -> tuple[argparse.Namespace, list[str], argparse.ArgumentParser]:
    parser = argparse.ArgumentParser(
        description="Block-based GTK4 editor with external Vim editing"
    )
    parser.add_argument("-v", "--version", action="store_true", help="Show version")
    parser.add_argument("-u", "--upgrade", action="store_true", help="Upgrade")
    parser.add_argument(
        "-e",
        "--export",
        nargs="?",
        const="__default__",
        help=(
            "Export .docv to HTML (optional output path; without input, "
            "export all .docv recursively from cwd)"
        ),
    )
    parser.add_argument(
        "-q", action="store_true", dest="demo", help="Quickstart content"
    )
    parser.add_argument("file", nargs="?", help=".docv document to open")
    if hasattr(parser, "parse_known_intermixed_args"):
        args, gtk_args = parser.parse_known_intermixed_args(argv)
    else:
        args, gtk_args = parser.parse_known_args(argv)
    return args, gtk_args, parser


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


def _run_init() -> int:
    root = Path.cwd()
    anchor = root / "__init__.docv"
    if anchor.exists() and not anchor.is_file():
        print("__init__.docv exists and is not a file", file=sys.stderr)
        return 1
    if not anchor.exists():
        try:
            document_io.save(anchor, BlockDocument([]))
        except OSError:
            print("Failed to create __init__.docv", file=sys.stderr)
            return 1
    added = config.add_vault(root)
    if added:
        print(f"Vault registered: {root}")
    else:
        print(f"Vault already registered: {root}")
    return 0


def _find_project_root() -> Path | None:
    current = Path.cwd()
    for candidate in [current, *current.parents]:
        if (candidate / "__init__.docv").exists():
            return candidate
    return None


def _vault_has_docs(root: Path) -> bool:
    try:
        for path in root.rglob("*.docv"):
            if path.name == "__init__.docv":
                continue
            return True
    except OSError:
        return False
    return False


def _run_export_all() -> int:
    root = _find_project_root()
    if root is None:
        print(
            "Export requires __init__.docv in the project root",
            file=sys.stderr,
        )
        return 1
    doc_paths = sorted(root.rglob("*.docv"))
    if not doc_paths:
        print(f"No .docv files found under {root}", file=sys.stderr)
        return 1
    python_path = config.get_python_path()
    ui_mode = config.get_ui_mode() or "dark"
    for doc_path in doc_paths:
        document = document_io.load(doc_path)
        export_document(document, doc_path.with_suffix(".html"), python_path, ui_mode)
    return 0


def _run_export(output_path: str, input_path: str | None) -> int:
    if not input_path:
        if output_path == "__default__":
            return _run_export_all()
        print("Export requires a .docv input path", file=sys.stderr)
        return 1
    if output_path == "__default__" or not output_path:
        output_path = str(Path(input_path).with_suffix(".html"))
    doc_path = Path(input_path).expanduser()
    if not doc_path.exists():
        print(f"Missing document: {doc_path}", file=sys.stderr)
        return 1
    document = document_io.load(doc_path)
    python_path = config.get_python_path()
    ui_mode = config.get_ui_mode() or "dark"
    export_document(document, Path(output_path).expanduser(), python_path, ui_mode)
    return 0
