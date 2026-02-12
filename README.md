# gtkv

`gtkv` is a GTK4 block-based editor that keeps Vim as the editor. Text and
images live in separate blocks, and text blocks open in an external terminal
Vim session for full editing power. Documents are stored as a single `.docv`
SQLite file.

---

## Requirements

- GTK4 runtime libraries.
- PyGObject + GObject Introspection (for running from source).
- A terminal Vim (`nvim`, `vim`, or `vi`).
- Optional: the `o` file picker for image insertion.

## Installation

### Prebuilt binary (Linux x86_64)

Grab the latest tagged release via the helper script:

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/gtkv/main/install.sh | bash
```

The script drops the unpacked bundle into `~/.gtkv/app` and a shim in
`~/.gtkv/bin`. It will attempt to append that directory to your `PATH` (unless
you opt out). Once installed, run `gtkv -h` to confirm everything works.

Installer flags of note:

- `-v <x.y.z>`: install a specific tagged release (`v0.2.0`, etc.).
- `-v` (no argument): print the latest GitHub release version.
- `-u`: reinstall only if GitHub has something newer than your current local copy.
- `-b /path/to/gtkv-linux-x64.tar.gz`: install from an already-downloaded archive.
- `-h`: show installer usage.

You can also download the `gtkv-linux-x64.tar.gz` artifact manually from the
releases page and run `install.sh --binary` if you prefer to manage the bundle
yourself.

### From source

```bash
git clone https://github.com/ryangerardwilson/gtkv.git
cd gtkv
python main.py
```

---

## Usage

- `gtkv` — start the editor.
- `gtkv doc.docv` — open an existing document.
- `Ctrl+V` — append a new text block.
- `Ctrl+I` — insert an image block via the `o` picker.
- `j/k` — move between blocks.
- `Enter` — open the selected text block in Vim.
- Exit Vim — refreshes the block content in GTK.
- `Ctrl+S` — save the current document (prompts for a path on first save).
- `-v` — print installed version.
- `-u` — upgrade to the latest release.
- `-h` — show CLI help.
- `--image /path/to/image.png` — include an image in the sample document.

### Bash completion

The installer drops a completion script into
`${XDG_CONFIG_HOME:-~/.config}/bash_completion.d/gtkv` and adds a loader to
`~/.bashrc` if needed.

---

## Notes

- Text and images are separate blocks; there is no inline mixing.
- Vim runs externally in your terminal; GTK stays focused on layout.
- Documents are stored as SQLite `.docv` files containing text blocks and image blobs.

---

## Releases

Tag the repository with the desired semantic version and push:

```bash
git tag v0.4.0
git push origin v0.4.0
```

GitHub Actions builds a source bundle (`gtkv-linux-x64.tar.gz`), updates
`_version.py`, and publishes the asset alongside the tagged release.
