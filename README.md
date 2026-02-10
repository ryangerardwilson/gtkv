# gtkv

`gtkv` is a GTK4-first Vim-inspired editor with inline image support. It saves
documents as `*.gtkv.html` with embedded base64 images, and keeps the workflow
fast and minimal.

---

## Requirements

- GTK4 runtime libraries.
- PyGObject + GObject Introspection (for running from source). Install via your distro package manager.

## Installation

### Prebuilt binary (Linux x86_64)

Grab the latest tagged release via the helper script:

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/gtkv/main/install.sh | bash
```

The script drops the unpacked bundle into `~/.gtkv/app` and a shim in
`~/.gtkv/bin`. It will attempt to append that directory to your `PATH` (unless
you opt out). Once installed, run `gtkv -h` to confirm everything works.

The installer will prompt for the Python interpreter path used to launch gtkv
(it should be a Python with GTK4 + PyGObject installed). The chosen path is
stored in `${XDG_CONFIG_HOME:-~/.config}/gtkv/config.json`.

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
- `gtkv file.gtkv.html` — open an existing document.
- `Ctrl+I` — insert an image.
- `Ctrl+S` — save (creates `*.gtkv.html`).
- `-v` — print installed version.
- `-u` — upgrade to the latest release.
- `-h` — show CLI help.

---

## Releases

Tag the repository with the desired semantic version and push:

```bash
git tag v0.4.0
git push origin v0.4.0
```

GitHub Actions builds a PyInstaller bundle (`gtkv-linux-x64.tar.gz`), updates
`_version.py`, and publishes the asset alongside the tagged release.
