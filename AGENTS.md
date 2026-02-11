# AGENTS

This file describes the single responsibility of each component, the goals and
non-goals of the project, and why the current architecture exists.

## Goals
- Preserve a Vim-first workflow in a GTK4 UI.
- Render inline images and text without visual glitches.
- Persist documents as HTML with embedded images that match the GTK view.
- Grow complexity by cleanly separating UI, editor state/modes, persistence, and services.
- Keep the codebase easy to refactor and evolve over time.

## Non-goals
- Full Vim parity (not a replacement for Vim or Neovim).
- Terminal emulation inside the app.
- Multi-pane window management or full IDE features.
- Rich HTML editing beyond the GTKV persistence format.

## Why the architecture exists
The app started as a proof of concept with most logic in `orchestrator.py`. As
features expanded (inline images, HTML persistence, modes, command pane), the
architecture was split into focused modules. This keeps the core orchestration
thin and makes it possible to scale rendering, persistence, and command
handling independently without reworking the whole app.

Recent changes continue that split by pushing cursor state into the editor
model and keeping rendering concerns in the view layer.

## Preferred project layout (flat)
- Keep the repo flat at the root; avoid deep package trees for core modules.
- Use prefixes to group components instead of folders:
  - `ui_*` for GTK UI concerns
  - `editor_*` for mode routing, document state, commands
  - `persistence_*` for file formats and serialization
  - `services_*` for caches, I/O helpers
  - `completions_*` for shell completion scripts

This layout makes browsing faster, keeps imports simple, and encourages focused
modules.

## Release + packaging workflow

### `.github/`
Holds GitHub Actions workflows for tagging and release packaging. The release
workflow builds the bundle and publishes artifacts to GitHub Releases.

### `install.sh`
Installer script that:
- downloads the tagged release bundle or installs from a local tarball
- installs into `~/.gtkv/app` and puts a launcher in `~/.gtkv/bin`
- optionally adds the bin directory to PATH
- installs bash completion from `completions_gtkv.bash`

### `_version.py`
Single source of installed version for the CLI (`gtkv --version`). Updated
during release packaging so the binary bundle reports the correct version.

## Components and single responsibility

### `orchestrator.py`
Top-level coordinator. Wires together UI, editor state, command controller, and
persistence. Contains no rendering logic beyond orchestration and routing.

### `ui_window_shell.py`
Owns the window layout, status bar, and command pane placement. Applies UI-
level CSS and window concerns.

### `ui_editor_view.py`
Owns GTK text rendering, inline image widgets, cursor/selection rendering, and
UI projection of document segments.

### `ui_command_pane.py`
Owns the bottom command UI, input widget, prefix display, and hint text.

### `ui_status_controller.py`
Keeps the status bar in sync with editor state and temporary hints.

### `editor_state.py`
Holds editor mode and file path state, and notifies listeners on changes.

### `editor_document.py`
Source of truth for document content, cursor/selection state, and model-level
navigation. Emits updates to views.

### `editor_mode_router.py`
Routes key presses to the correct mode handler based on current state.

### `editor_commands_normal.py`
Normal-mode key handling (e.g., `i`, `v`, `hjkl`).

### `editor_commands_insert.py`
Insert-mode key handling (escape, inline delete, optional movement).

### `editor_commands_visual.py`
Visual-mode key handling and selection movement.

### `editor_command_controller.py`
Owns command pane lifecycle, history, and `/` incremental search behavior.

### `editor_command_parser.py`
Parses ex-style `:` commands into command + args.

### `persistence_gtkv_html.py`
Builds and parses the GTKV HTML persistence format.

### `services_image_cache.py`
Materializes data URIs to cache files and cleans up cached images.

### `logging_debug.py`
Debug logging setup, GLib logging capture, crash hooks, and action ring buffer.

### `config.py`
Holds runtime configuration (flags, cache limits, debug toggle).

### `main.py`
CLI entry point; parses flags, initializes logging, and starts the GTK app.
