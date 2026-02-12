# AGENTS

This file describes the single responsibility of each component, the goals and
non-goals of the project, and why the current architecture exists.

## Goals
- Preserve a Vim-first workflow by delegating editing to an external terminal Vim.
- Render a block-based GTK4 UI where text blocks and image blocks never share a line.
- Keep the core GTK app focused on layout, navigation, and block orchestration.
- Minimize internal editor logic and keep the codebase easy to refactor.
- Persist documents as a single SQLite `.docv` file with embedded image blobs and 3D block sources.

## Non-goals
- Inline image rendering inside text lines.
- Reimplementing Vim behaviors in GTK.
- Terminal emulation inside the app.
- Multi-pane window management or full IDE features.

## Why the architecture exists
The app now treats editing as an external concern. GTK is responsible for
document layout and navigation across blocks, while Vim runs in a separate
terminal against temporary files. This keeps the UI simple and eliminates the
need to recreate Vim modes internally.

## Preferred project layout (flat)
- Keep the repo flat at the root; avoid deep package trees for core modules.
- Use direct, single-purpose modules:
  - `main.py` for CLI + app startup
  - `block_model.py` for block data structures
  - `block_view.py` for GTK rendering + navigation
  - `style.css` for UI styling
  - `three_template.py` for 3D block HTML boilerplate
  - `three.module.min.js` for bundled Three.js
  - `completions_gtkv.bash` for shell completion

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

### `main.py`
CLI entry point. Parses flags, manages upgrade/version flows, and starts the GTK app.

### `block_model.py`
Defines block types and the document structure.

### `block_view.py`
Renders the document as GTK blocks and tracks selection/navigation.

### `persistence_sqlite.py`
SQLite persistence for `.docv` files (text, image, and 3D blocks).

### `style.css`
Visual styling for the block UI.
