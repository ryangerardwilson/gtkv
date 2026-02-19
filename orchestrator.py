"""Application orchestration and GTK setup."""

from __future__ import annotations

import argparse
import logging
import threading
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Sequence

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # type: ignore[import-not-found, attr-defined]

import actions
import config
import keymap
from loading_screen import LoadingScreen
import document_io
import editor
import py_runner
from export_html import (
    build_index_link_id,
    build_index_tree_html,
    export_document,
    export_vault_index,
)
from design_constants import colors_for, font
from _version import __version__
from app_state import AppState
from block_model import (
    BlockDocument,
    MapBlock,
    PythonImageBlock,
    TextBlock,
    get_document_title,
    sample_document,
)
from block_view import BlockEditorView


INSTALL_SH_URL = (
    "https://raw.githubusercontent.com/ryangerardwilson/gvim/main/install.sh"
)
APP_ID = "com.gvim.block"


class BlockApp(Gtk.Application):
    def __init__(self, orchestrator: "Orchestrator") -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self._orchestrator = orchestrator

    def do_activate(self) -> None:
        logging.info("GTK activate")
        window = Gtk.ApplicationWindow(application=self)
        try:
            self._orchestrator.configure_window(window)
        except Exception:
            logging.error("Configure window failed:\n%s", traceback.format_exc())
            raise


class Orchestrator:
    def __init__(self) -> None:
        self._state = AppState()
        self._python_path: str | None = None
        self._ui_mode: str | None = None
        self._keymap = keymap.load_keymap()
        self._mode = "document"
        self._open_vault_on_start = False
        self._active_vault_root: Path | None = None
        self._pyimage_error_cache: dict[int, str] = {}
        self._pyimage_render_tokens: dict[int, int] = {}
        self._startup_loading: LoadingScreen | None = None
        self._startup_pyimage_pending: set[int] = set()
        self._demo = False
        self._deploy_running = False
        self._vault_locked = False

    def run(self, argv: Sequence[str] | None = None) -> int:
        logging.info("Orchestrator run")
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
        self._python_path = _get_venv_python()

        self._ui_mode = config.get_ui_mode()
        logging.info("UI mode from config: %s", self._ui_mode)
        if not self._ui_mode:
            self._ui_mode = _prompt_ui_mode_cli()
            if self._ui_mode:
                config.set_ui_mode(self._ui_mode)
        logging.info("UI mode resolved: %s", self._ui_mode)

        cwd_vault_root = _find_config_vault_for_path(Path.cwd())
        if document_path is not None and document_path.exists():
            if self._demo:
                print(
                    "Quickstart only applies to new files; remove -q to open an existing document.",
                    file=sys.stderr,
                )
                return 1
            vault_root = _find_config_vault_for_path(document_path)
            if vault_root is None:
                print(
                    "This file is not inside a configured gvim vault. Register a vault with 'gvim init', then re-run this command.",
                    file=sys.stderr,
                )
                return 1
            self._active_vault_root = vault_root
            self._vault_locked = True
            self._state.document = document_io.load(document_path)
        else:
            if document_path is not None:
                if self._demo:
                    self._state.document = sample_document()
                else:
                    self._state.document = BlockDocument(
                        [TextBlock("Untitled", kind="title")]
                    )
                self._state.document.set_path(document_path)
                self._active_vault_root = cwd_vault_root
                if self._active_vault_root is not None:
                    self._vault_locked = True
                document_io.save(document_path, self._state.document)
            else:
                self._state.document = BlockDocument(
                    [TextBlock("Untitled", kind="title")]
                )
                vaults = [path for path in config.get_vaults() if path.exists()]
                if vaults:
                    self._active_vault_root = cwd_vault_root
                    self._open_vault_on_start = True

        app = BlockApp(self)
        logging.info("GTK app initialized; ui_mode=%s", self._ui_mode)
        logging.info("GTK app run; gtk_args=%s", gtk_args)
        argv = [sys.argv[0], *gtk_args]
        rc = app.run(argv)
        registered = app.get_is_registered()
        remote = app.get_is_remote() if registered else None
        logging.info(
            "GTK app exit: %s (registered=%s remote=%s)", rc, registered, remote
        )
        return rc

    def configure_window(self, window: Gtk.ApplicationWindow) -> None:
        logging.info("Configure window")
        settings = Gtk.Settings.get_default()
        if settings is not None:
            settings.set_property(
                "gtk-application-prefer-dark-theme",
                (self._ui_mode or "dark") == "dark",
            )
            logging.info(
                "GTK prefer-dark-theme: %s",
                (self._ui_mode or "dark") == "dark",
            )
        _load_css(
            Path(__file__).with_name("style.css"),
            self._ui_mode or "dark",
            window.get_display(),
        )
        window.set_title("GVIM")
        window.set_default_size(960, 720)

        loading = LoadingScreen(self._ui_mode or "dark")
        self._startup_loading = loading
        window.set_child(loading.container)

        document = self._state.document
        if document is None:
            document = BlockDocument([TextBlock("Untitled", kind="title")])
            self._state.document = document

        view: BlockEditorView = BlockEditorView(
            self._ui_mode or "dark",
            self._keymap,
            demo=self._demo,
        )
        view.set_document(document)
        self._state.view = view
        logging.info("View created; blocks=%s", len(document.blocks))
        self._prime_startup_loading(document)
        self._render_python_images_on_start()
        loading.attach_content(view)
        self._finish_startup_loading_if_ready()
        if self._open_vault_on_start:
            self._open_vault_on_start = False
            self._open_vault_mode()

        controller = Gtk.EventControllerKey()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect("key-pressed", self.on_key_pressed)
        window.add_controller(controller)

        window.set_child(view)
        window.present()
        logging.info("Window presented")

    def on_key_pressed(self, _controller, keyval, _keycode, state) -> bool:
        if self._state.document is None or self._state.view is None:
            return False

        if self._mode == "vault":
            action = self._state.view.handle_vault_key(keyval, state)
            if action.opened_path is not None:
                self._open_document_path(action.opened_path)
                self._close_vault_mode()
            elif action.close:
                self._close_vault_mode()
            if action.selected_vault_root is not None:
                self._active_vault_root = action.selected_vault_root
                self._vault_locked = True
            if action.locked:
                self._show_status("Vault locked for session", "success")
            if action.toggle_theme:
                self._toggle_ui_mode()
            return action.handled

        if self._state.view.handle_help_key(keyval, state):
            return True

        return self._handle_doc_keys(keyval, state)

    def _handle_doc_keys(self, keyval, state) -> bool:
        if self._state.view is not None and self._state.view.toc_drill_active():
            return self._state.view.handle_toc_drill_key(keyval, state)
        token = keymap.event_to_token(keyval, state)
        if token is None:
            return False
        action, handled = self._keymap.match("document", token)
        if not handled:
            return False
        if action is None:
            return True
        return self._dispatch_doc_action(action)

    def _dispatch_doc_action(self, action: str) -> bool:
        if action == "move_down":
            return actions.move_selection(self._state, 1)
        if action == "move_up":
            return actions.move_selection(self._state, -1)
        if action == "move_block_down":
            if actions.move_block(self._state, 1):
                self._persist_document()
                return True
            return False
        if action == "move_block_up":
            if actions.move_block(self._state, -1):
                self._persist_document()
                return True
            return False
        if action == "first_block":
            return actions.select_first(self._state)
        if action == "last_block":
            return actions.select_last(self._state)
        if action == "open_editor":
            return self._open_selected_block_editor()
        if action == "quit_no_save":
            self._quit()
            return True
        if action == "export_html":
            if self._export_current_html():
                self._show_status("Exported HTML", "success")
            else:
                self._show_status("Export failed", "error")
            return True
        if action == "deploy_sync":
            self._deploy_sync()
            return True
        if action == "help_toggle":
            if self._state.view is not None:
                self._state.view.toggle_help()
            return True
        if action == "paste_block":
            if self._state.clipboard_block is None:
                self._show_status("Nothing to paste", "error")
                return True
            if actions.paste_after_selected(self._state, self._state.clipboard_block):
                self._show_status("Pasted block", "success")
                self._persist_document()
            else:
                self._show_status("Paste failed", "error")
            return True
        if action == "delete_block":
            deleted = actions.delete_selected_block(self._state)
            if deleted is None:
                self._show_status("Nothing to delete", "error")
                return True
            self._state.clipboard_block = deleted
            self._show_status("Deleted block", "success")
            self._persist_document()
            return True
        if action == "yank_block":
            yanked = actions.yank_selected_block(self._state)
            if yanked is None:
                self._show_status("Nothing to yank", "error")
                return True
            self._state.clipboard_block = yanked
            self._show_status("Yanked block", "success")
            return True
        if action == "toggle_theme":
            self._toggle_ui_mode()
            return True
        if action == "open_vault":
            return self._open_vault_mode()
        if action == "open_toc":
            return self._open_toc_drill()
        if action == "insert_text":
            if actions.insert_text_block(self._state, kind="body"):
                self._persist_document()
                return True
            return False
        if action == "insert_title":
            if actions.insert_text_block(self._state, kind="title"):
                self._persist_document()
                return True
            return False
        if action == "insert_h1":
            if actions.insert_text_block(self._state, kind="h1"):
                self._persist_document()
                return True
            return False
        if action == "insert_h2":
            if actions.insert_text_block(self._state, kind="h2"):
                self._persist_document()
                return True
            return False
        if action == "insert_h3":
            if actions.insert_text_block(self._state, kind="h3"):
                self._persist_document()
                return True
            return False
        if action == "insert_h4":
            if actions.insert_text_block(self._state, kind="h4"):
                self._persist_document()
                return True
            return False
        if action == "insert_h5":
            if actions.insert_text_block(self._state, kind="h5"):
                self._persist_document()
                return True
            return False
        if action == "insert_h6":
            if actions.insert_text_block(self._state, kind="h6"):
                self._persist_document()
                return True
            return False
        if action == "insert_h4":
            if actions.insert_text_block(self._state, kind="h4"):
                self._persist_document()
                return True
            return False
        if action == "insert_h5":
            if actions.insert_text_block(self._state, kind="h5"):
                self._persist_document()
                return True
            return False
        if action == "insert_h6":
            if actions.insert_text_block(self._state, kind="h6"):
                self._persist_document()
                return True
            return False
        if action == "insert_toc":
            if actions.insert_toc_block(self._state):
                self._persist_document()
                return True
            return False
        if action == "insert_three":
            if self._insert_three_block():
                self._persist_document()
                return True
            return False
        if action == "insert_pyimage":
            if self._insert_python_image_block():
                self._persist_document()
                return True
            return False
        if action == "insert_latex":
            if self._insert_latex_block():
                self._persist_document()
                return True
            return False
        if action == "insert_map":
            if self._insert_map_block():
                self._persist_document()
                return True
            return False
        return False

    def _open_toc_drill(self) -> bool:
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
            self._persist_document()
        self._state.view.open_toc_drill(self._state.document)
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
        if self._active_vault_root is not None:
            vaults = [self._active_vault_root]
        else:
            vaults = [path for path in config.get_vaults() if path.exists()]
        if not vaults:
            self._show_status("No vaults registered", "error")
            return True
        if self._vault_locked and self._active_vault_root is not None:
            vaults = [self._active_vault_root]
        self._mode = "vault"
        self._state.view.open_vault_mode(vaults, locked=self._vault_locked)
        if self._active_vault_root is not None:
            self._vault_locked = True
        return True

    def _close_vault_mode(self) -> None:
        if self._state.view is None:
            return
        if self._state.document is None or self._state.document.path is None:
            self._show_status("Open a document first", "error")
            vaults = [path for path in config.get_vaults() if path.exists()]
            if vaults:
                self._state.view.open_vault_mode(vaults)
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
        self._persist_document()
        if kind == "pyimage":
            if self._state.view is not None:
                self._state.view.set_pyimage_pending(index)
            self._start_python_image_render(index)
            return
        view = self._state.view
        if view is None:
            return
        if kind == "text":
            view.update_text_at(index, updated_text)
            document = self._state.document
            if document is None:
                return
            if index < 0 or index >= len(document.blocks):
                return
            block = document.blocks[index]
            if isinstance(block, TextBlock) and block.kind in {
                "title",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
            }:
                view.refresh_toc(document)
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

    def _save_document(self) -> tuple[bool, str | None]:
        document = self._state.document
        if document is None:
            return False, "Missing document"
        if not get_document_title(document):
            return False, "Title required"
        if document.path is not None:
            document_io.save(document.path, document)
            return True, None
        return False, "No document path set; launch with a .gvim filename"

    def _persist_document(self) -> bool:
        saved, error = self._save_document()
        if not saved and error:
            self._show_status(error, "error")
        return saved

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

    def _deploy_sync(self) -> None:
        if self._deploy_running:
            self._show_status("Deploy already running", "error")
            return
        root = self._resolve_vault_root_for_sync()
        if root is None:
            self._show_status("Deploy requires a configured vault", "error")
            return
        if shutil.which("git") is None:
            self._show_status("Git not found", "error")
            return
        if not _git_is_repo(root):
            self._show_status("Git not initialized in vault", "error")
            return
        if not _git_has_remote(root):
            self._show_status("No git remote configured", "error")
            return
        self._deploy_running = True
        self._show_status("Deploying...", "success")

        def _worker() -> None:
            export_rc = _run_export_all_for_root(root)
            if export_rc != 0:
                result = export_rc
            else:
                result = _run_git_sync(root, allow_prompt=False)

            def _done() -> bool:
                self._deploy_running = False
                if result == 0:
                    self._show_status("Deployed", "success")
                else:
                    self._show_status("Deploy failed", "error")
                return False

            GLib.idle_add(_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _resolve_vault_root_for_sync(self) -> Path | None:
        if self._active_vault_root is not None:
            return self._active_vault_root
        document = self._state.document
        if document is None or document.path is None:
            return None
        return _find_config_vault_for_path(document.path)

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
            view.reload_media_at(index)
            self._mark_startup_pyimage_done(index)
            return

        dark = py_runner.render_python_image(
            block.source, python_path, block.format, ui_mode="dark"
        )
        light = py_runner.render_python_image(
            block.source, python_path, block.format, ui_mode="light"
        )
        self._apply_python_image_render(index, block.source, dark, light)

    def _start_python_image_render(self, index: int) -> None:
        document = self._state.document
        if document is None:
            return
        if index < 0 or index >= len(document.blocks):
            return
        block = document.blocks[index]
        if not isinstance(block, PythonImageBlock):
            return
        token = self._pyimage_render_tokens.get(index, 0) + 1
        self._pyimage_render_tokens[index] = token
        source = block.source
        render_format = block.format
        python_path = self._python_path
        if not python_path:
            self._render_python_image(index)
            return

        def _run() -> None:
            dark = py_runner.render_python_image(
                source, python_path, render_format, ui_mode="dark"
            )
            light = py_runner.render_python_image(
                source, python_path, render_format, ui_mode="light"
            )
            GLib.idle_add(
                lambda: self._apply_python_image_render(
                    index, source, dark, light, token
                )
            )

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _apply_python_image_render(
        self,
        index: int,
        source: str,
        dark: py_runner.RenderResult,
        light: py_runner.RenderResult,
        token: int | None = None,
    ) -> None:
        current = self._pyimage_render_tokens.get(index)
        if token is not None and current is not None and token != current:
            return
        document = self._state.document
        view = self._state.view
        if document is None or view is None:
            return
        if index < 0 or index >= len(document.blocks):
            return
        block = document.blocks[index]
        if not isinstance(block, PythonImageBlock):
            return
        if block.source != source:
            return
        error = dark.error or light.error
        if error:
            self._pyimage_error_cache[index] = error
            self._inject_pyimage_error(index, error)
        else:
            if index in self._pyimage_error_cache:
                del self._pyimage_error_cache[index]
            self._clear_pyimage_error(index)
        document.set_python_image_render(
            index,
            rendered_data_dark=dark.rendered_data,
            rendered_hash_dark=dark.rendered_hash,
            rendered_data_light=light.rendered_data,
            rendered_hash_light=light.rendered_hash,
            last_error=error,
        )
        view.reload_media_at(index)
        self._mark_startup_pyimage_done(index)

    def _inject_pyimage_error(self, index: int, error: str) -> None:
        document = self._state.document
        if document is None:
            return
        if index < 0 or index >= len(document.blocks):
            return
        block = document.blocks[index]
        if not isinstance(block, PythonImageBlock):
            return
        header = f'"""\nLAST RUNTIME ERROR: {error}\n"""\n'
        source = self._strip_pyimage_error(block.source)
        document.set_python_image_block(index, f"{header}{source}")

    def _clear_pyimage_error(self, index: int) -> None:
        document = self._state.document
        if document is None:
            return
        if index < 0 or index >= len(document.blocks):
            return
        block = document.blocks[index]
        if not isinstance(block, PythonImageBlock):
            return
        source = self._strip_pyimage_error(block.source)
        if source != block.source:
            document.set_python_image_block(index, source)

    @staticmethod
    def _strip_pyimage_error(source: str) -> str:
        prefix = '"""\nLAST RUNTIME ERROR:'
        if not source.startswith(prefix):
            return source
        end = source.find('"""', len(prefix))
        if end == -1:
            return source
        trimmed = source[end + 3 :]
        return trimmed.lstrip("\n")

    def _render_python_images_on_start(self) -> None:
        document = self._state.document
        if document is None:
            return
        for index, block in enumerate(document.blocks):
            if isinstance(block, PythonImageBlock):
                self._start_python_image_render(index)

    def _prime_startup_loading(self, document: BlockDocument) -> None:
        self._startup_pyimage_pending = {
            index
            for index, block in enumerate(document.blocks)
            if isinstance(block, PythonImageBlock)
        }
        if not self._startup_pyimage_pending:
            GLib.idle_add(self._finish_startup_loading_if_ready)

    def _mark_startup_pyimage_done(self, index: int) -> None:
        if index in self._startup_pyimage_pending:
            self._startup_pyimage_pending.discard(index)
            self._finish_startup_loading_if_ready()

    def _finish_startup_loading_if_ready(self) -> bool:
        if self._startup_loading is None:
            return False
        if self._startup_pyimage_pending:
            return False
        self._startup_loading.finish_when_ready()
        self._startup_loading = None
        return False


def _load_css(css_path: Path, ui_mode: str, display: Gdk.Display | None = None) -> None:
    if not css_path.exists():
        return

    logging.info("Loading CSS: %s (mode=%s)", css_path, ui_mode)
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
    variables += f"  --block-h4-color: {palette.block_h4};\n"
    variables += f"  --block-h4-size: {font.block_h4};\n"
    variables += f"  --block-h5-color: {palette.block_h5};\n"
    variables += f"  --block-h5-size: {font.block_h5};\n"
    variables += f"  --block-h6-color: {palette.block_h6};\n"
    variables += f"  --block-h6-size: {font.block_h6};\n"
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
    variables += (
        f"  --vault-row-selected-border: {palette.vault_row_selected_border};\n"
    )
    variables += f"  --vault-row-label-color: {palette.vault_row_label};\n"
    variables += f"  --vault-row-size: {font.vault_row};\n"
    variables += f"  --vault-empty-color: {palette.vault_empty};\n"
    variables += f"  --vault-empty-size: {font.vault_empty};\n"
    variables += f"  --vault-entry-background: {palette.vault_entry_background};\n"
    variables += f"  --vault-entry-border: {palette.vault_entry_border};\n"
    variables += f"  --vault-entry-text: {palette.vault_entry_text};\n"
    variables += f"  --vault-entry-placeholder: {palette.vault_entry_placeholder};\n"
    variables += f"  --vault-entry-focus: {palette.vault_entry_focus};\n"
    variables += f"  --loading-background: {palette.loading_background};\n"
    variables += f"  --loading-rain-primary: {palette.loading_rain_primary};\n"
    variables += f"  --loading-rain-secondary: {palette.loading_rain_secondary};\n"
    variables += f"  --loading-ascii-color: {palette.loading_ascii};\n"
    variables += f"  --loading-ascii-size: {font.loading_ascii};\n"
    variables += f"  --status-background: {palette.status_background};\n"
    variables += f"  --status-border: {palette.status_border};\n"
    variables += f"  --status-text-color: {palette.status_text};\n"
    variables += f"  --status-size: {font.status};\n"
    variables += f"  --status-success-color: {palette.status_success};\n"
    variables += f"  --status-error-color: {palette.status_error};\n"
    variables += "}\n"

    provider = Gtk.CssProvider()
    provider.load_from_data(variables.encode("utf-8"))
    if display is None:
        display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        logging.info("CSS variables applied")
    else:
        logging.info("CSS variables skipped; display not ready")

    provider = Gtk.CssProvider()
    provider.load_from_path(str(css_path))
    if display is None:
        display = Gdk.Display.get_default()
    if display is None:
        logging.info("CSS file skipped; display not ready")
        return

    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    logging.info("CSS file applied")


def _get_venv_python() -> str | None:
    venv_python = Path.home() / ".gvim" / "venv" / "bin" / "python"
    if venv_python.exists() and os.access(venv_python, os.X_OK):
        return str(venv_python)
    return None


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
        help=("Export all .gvim recursively from the current vault"),
    )
    parser.add_argument(
        "-q",
        action="store_true",
        dest="demo",
        help="Quickstart content for new files",
    )
    parser.add_argument("file", nargs="?", help=".gvim document to open")
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
    vaults = [path.resolve() for path in config.get_vaults() if path.exists()]
    root_resolved = root.resolve()
    already_registered = False
    for vault in vaults:
        if root_resolved == vault:
            print(f"Vault already registered: {root}")
            already_registered = True
            break
        if vault in root_resolved.parents:
            print(
                "Cannot initialize a vault here: this directory is already inside a configured vault. Run 'gvim init' at the vault root instead.",
            )
            return 1
        if root_resolved in vault.parents:
            print(
                "Cannot initialize a vault here: this directory contains a configured vault. Remove the nested vault before initializing here.",
            )
            return 1
    if not already_registered:
        added = config.add_vault(root)
        if added:
            print(f"Vault registered: {root}")
        else:
            print(f"Vault already registered: {root}")
    git_rc = _run_git_sync(root)
    if git_rc != 0:
        return git_rc
    if _prompt_pages_setup():
        if not _setup_pages_workflow(root):
            return 1
        if not _git_stage_all(root):
            return 1
        _git_commit_sync(root)
        if not _git_push(root):
            return 1
        print("GitHub Pages workflow added. Set Pages source to GitHub Actions.")
    return 0


def _find_config_vault_for_path(path: Path) -> Path | None:
    vaults = [vault.resolve() for vault in config.get_vaults() if vault.exists()]
    if not vaults:
        return None
    resolved_path = path.resolve()
    for vault in vaults:
        if resolved_path == vault or vault in resolved_path.parents:
            return vault
    return None


def _run_git_sync(root: Path, allow_prompt: bool = True) -> int:
    if shutil.which("git") is None:
        print("Git not found; skipping sync.", file=sys.stderr)
        return 1
    if not _git_is_repo(root):
        if not _git_init(root):
            return 1
    if not _git_stage_all(root):
        return 1
    _git_commit_sync(root)
    if not _git_has_remote(root):
        if not allow_prompt:
            print("Missing git remote; skipping push.", file=sys.stderr)
            return 1
        remote = input("Git remote URL: ").strip()
        if not remote:
            print("Missing remote URL; skipping push.", file=sys.stderr)
            return 1
        if not _git_add_remote(root, remote):
            return 1
    if not _git_has_head(root):
        print("No commits to push.", file=sys.stderr)
        return 0
    if not _git_push(root):
        return 1
    return 0


def _git_is_repo(root: Path) -> bool:
    if (root / ".git").exists():
        return True
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return False
    try:
        return Path(result.stdout.strip()).resolve() == root.resolve()
    except OSError:
        return False


def _git_init(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "init", "-b", "main"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "Git init failed", file=sys.stderr)
        return False
    return True


def _git_stage_all(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "add", "."],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "Git add failed", file=sys.stderr)
        return False
    return True


def _git_commit_sync(root: Path) -> None:
    result = subprocess.run(
        ["git", "-C", str(root), "commit", "-m", "sync"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode == 0:
        return
    combined = f"{result.stdout}\n{result.stderr}".lower()
    if "nothing to commit" in combined:
        return
    print(result.stderr.strip() or "Git commit failed", file=sys.stderr)


def _git_has_remote(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "remote", "get-url", "origin"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0


def _git_add_remote(root: Path, remote: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "remote", "add", "origin", remote],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "Failed to add remote", file=sys.stderr)
        return False
    return True


def _git_has_head(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0


def _git_push(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "push", "-u", "origin", "HEAD"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "Git push failed", file=sys.stderr)
        return False
    return True


def _prompt_pages_setup() -> bool:
    try:
        answer = input("Set up GitHub Pages deployment (public site)? (y/N): ").strip()
    except EOFError:
        return False
    return answer.lower() in {"y", "yes"}


def _setup_pages_workflow(root: Path) -> bool:
    workflows_dir = root / ".github" / "workflows"
    workflow_path = workflows_dir / "pages.yml"
    if workflow_path.exists():
        print("Pages workflow already exists; skipping.")
        return True
    try:
        workflows_dir.mkdir(parents=True, exist_ok=True)
        workflow_path.write_text(_pages_workflow_yaml(), encoding="utf-8")
    except OSError as exc:
        print(f"Failed to write workflow: {exc}", file=sys.stderr)
        return False
    return True


def _pages_workflow_yaml() -> str:
    return (
        "name: Deploy Pages\n"
        "on:\n"
        "  push:\n"
        "    branches: [main]\n"
        "permissions:\n"
        "  contents: read\n"
        "  pages: write\n"
        "  id-token: write\n"
        "concurrency:\n"
        "  group: pages\n"
        "  cancel-in-progress: false\n"
        "jobs:\n"
        "  deploy:\n"
        "    runs-on: ubuntu-latest\n"
        "    environment:\n"
        "      name: github-pages\n"
        "      url: ${{ steps.deployment.outputs.page_url }}\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/configure-pages@v5\n"
        "      - uses: actions/upload-pages-artifact@v3\n"
        "        with:\n"
        "          path: .\n"
        "      - id: deployment\n"
        "        uses: actions/deploy-pages@v4\n"
    )


def _run_export_all() -> int:
    root = _find_config_vault_for_path(Path.cwd())
    if root is None:
        print(
            "Export requires a configured vault. Run 'gvim init' in the vault root.",
            file=sys.stderr,
        )
        return 1
    return _run_export_all_for_root(root)


def _run_export_all_for_root(root: Path) -> int:
    doc_paths = sorted(root.rglob("*.gvim"))
    if not doc_paths:
        print(f"No .gvim files found under {root}", file=sys.stderr)
        return 1
    python_path = _get_venv_python()
    ui_mode = config.get_ui_mode() or "dark"
    export_items: list[tuple[Path, BlockDocument, str | None]] = []
    index_items: list[tuple[Path, str | None]] = []
    for doc_path in doc_paths:
        document = document_io.load(doc_path)
        output_path = doc_path.with_suffix(".html")
        title = get_document_title(document)
        export_items.append((output_path, document, title))
        index_items.append((output_path, title))

    rel_index_items = [
        (path.relative_to(root), title or path.stem or path.name)
        for path, title in index_items
    ]

    for output_path, document, _title in export_items:
        rel_output = output_path.relative_to(root)
        depth = max(len(rel_output.parts) - 1, 0)
        base_prefix = "../" * depth
        index_href = f"{base_prefix}index.html#{build_index_link_id(rel_output)}"
        index_tree_html = build_index_tree_html(rel_index_items, base_prefix)
        export_document(
            document,
            output_path,
            python_path,
            ui_mode,
            index_tree_html=index_tree_html,
            index_href=index_href,
        )

    export_vault_index(root, index_items, ui_mode)
    _cleanup_orphan_html(root, [path for path, _title in index_items])
    return 0


def _cleanup_orphan_html(root: Path, html_paths: list[Path]) -> None:
    keep = {path.resolve() for path in html_paths}
    index_path = (root / "index.html").resolve()
    for html_path in root.rglob("*.html"):
        resolved = html_path.resolve()
        if resolved == index_path:
            continue
        if resolved in keep:
            continue
        try:
            html_path.unlink()
        except OSError:
            continue


def _run_export(output_path: str, input_path: str | None) -> int:
    if input_path:
        print(
            "Export requires running inside a configured vault; omit the input path.",
            file=sys.stderr,
        )
        return 1
    if output_path != "__default__":
        print(
            "Export does not accept a custom output path; use gvim -e from the vault root.",
            file=sys.stderr,
        )
        return 1
    return _run_export_all()
