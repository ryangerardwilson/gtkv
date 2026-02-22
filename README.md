# gvim

`gvim` is a GTK4 block-based editor that keeps Vim as the editor. Text and code
live in separate blocks, and text blocks open in an external terminal Vim
session for full editing power. Documents are stored as a git-friendly text
`.gvim` file. 3D and LaTeX blocks render with WebKitGTK.

---

## Requirements

- GTK4 runtime libraries.
- PyGObject + GObject Introspection (for running from source).
- A terminal Vim (`nvim`, `vim`, or `vi`).
- Optional: WebKitGTK for 3D blocks.
- Optional: Python + Matplotlib for Python render blocks.
- Optional: WebKitGTK for LaTeX blocks (bundled KaTeX assets).
- Bundled: `three.module.min.js` is included for 3D blocks.
- Bundled: KaTeX assets (`katex.min.js`, `katex.min.css`, `fonts/`) for LaTeX.

### Distros where it should "just work"

The installer auto-installs system dependencies on these Linux distros:

- Ubuntu / Debian
- Fedora
- Arch

On other distros (NixOS, Gentoo, Alpine, etc.), install GTK4 + PyGObject
manually and run from source or use the binary with a compatible runtime.

## Installation

### Prebuilt binary (Linux x86_64)

Grab the latest tagged release via the helper script:

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/gvim/main/install.sh | bash
```

The script drops the unpacked bundle into `~/.gvim/app` and a shim in
`~/.gvim/bin`. It will attempt to append that directory to your `PATH` (unless
you opt out). Once installed, run `gvim -h` to confirm everything works.

The installer also creates a dedicated venv at `~/.gvim/venv`, installs
PyGObject via pip, and wires the launcher to always use that venv.

Installer flags of note:

- `-v <x.y.z>`: install a specific tagged release (`v0.2.0`, etc.).
- `-v` (no argument): print the latest GitHub release version.
- `-u`: reinstall only if GitHub has something newer than your current local copy.
- `-b /path/to/gvim-linux-x64.tar.gz`: install from an already-downloaded archive.
- `-h`: show installer usage.

You can also download the `gvim-linux-x64.tar.gz` artifact manually from the
releases page and run `install.sh --binary` if you prefer to manage the bundle
yourself.

### From source

```bash
git clone https://github.com/ryangerardwilson/gvim.git
cd gvim
python main.py
```

System dependencies are required for PyGObject and GTK4. The installer uses
`sudo` to install them for supported distros.

---

## Usage

- `gvim` — open a new document.
- `gvim doc.gvim` — open an existing document.
- `gvim init` — register the current directory as a vault.
- `,bn` — insert a normal text block.
- `,bht` — insert a title block.
- `,bh1` / `,bh2` / `,bh3` — insert heading blocks.
- `,bh4` / `,bh5` / `,bh6` — insert smaller heading blocks.
- `,bi` — insert an index block.
- `,bjs` — insert a 3D block and edit its Three.js module JS in Vim.
- `,bpy` — insert a Python render block (SVG output).
- `,bltx` — insert a LaTeX block rendered with KaTeX.
- `,bmap` — insert a map block (Leaflet JS).
- `j/k` — move between blocks.
- `,j` — jump to the last block.
- `,k` — jump to the first block.
- `,i` — open the index drill.
- `,v` — open vault mode.
- `,m` — toggle light/dark mode.
- `Ctrl+j/k` — move the selected block up/down.
- `dd` — cut the selected block.
- `yy` — yank the selected block.
- `p` — paste the clipboard block after the selection.
- `v` — visual mode to select multiple blocks with `j/k`, then `d` or `y`.
- `Enter` — open the selected text or code block in Vim.
- `Enter` on a TOC block — open the outline drill.
- Exit Vim — refreshes the block content in GTK.
- `Ctrl+D` — deploy (git add/commit/push) from the vault.
- `Ctrl+Q` / `q` — quit.
- `Escape` — return to document mode from vault mode.
- `-v` — print installed version.
- `-u` — upgrade to the latest release.
- `-q` — quickstart a new document with demo content (new files only).
- `-h` — show CLI help.

## Configuration

`gvim` stores settings in `~/.config/gvim/config.json` (or
`$XDG_CONFIG_HOME/gvim/config.json`). You can edit this file to customize the
Vim-style keymap and leader.

Edits are persisted automatically whenever you change a block.

## GitHub Actions Deploy

`Ctrl+D` runs the deploy pipeline from your vault root: it exports the full
static site, then runs `git add .`, `git commit -m "sync"`, and `git push`.
Pair this with the optional GitHub Actions workflow created during `gvim init`
to publish the latest HTML on every push.

Example `config.json` with keymap overrides:

```json
{
  "mode": "dark",
  "vaults": ["/path/to/vault"],
  "keymap": {
    "leader": ",",
    "modes": {
      "document": {
        "move_down": "j",
        "move_up": "k",
        "move_block_down": "<C-j>",
        "move_block_up": "<C-k>",
        "first_block": "gg",
        "last_block": "G",
        "open_editor": "<CR>",
        "quit_no_save": "q",
        "quit": "<C-q>",
        "deploy_sync": "<C-d>",
        "help_toggle": "?",
        "paste_block": "p",
        "delete_block": "dd",
        "yank_block": "yy",
        "toggle_theme": "<leader>m",
        "open_vault": "<leader>v",
        "open_toc": "<leader>i",
        "insert_text": "<leader>bn",
        "insert_title": "<leader>bht",
        "insert_h1": "<leader>bh1",
        "insert_h2": "<leader>bh2",
        "insert_h3": "<leader>bh3",
        "insert_h4": "<leader>bh4",
        "insert_h5": "<leader>bh5",
        "insert_h6": "<leader>bh6",
        "insert_toc": "<leader>bi",
        "insert_three": "<leader>bjs",
        "insert_pyimage": "<leader>bpy",
        "insert_latex": "<leader>bltx",
        "insert_map": "<leader>bmap"
      },
      "visual": {
        "move_down": "j",
        "move_up": "k",
        "delete_range": "d",
        "yank_range": "y",
        "exit_visual": "v",
        "paste_block": "p"
      },
      "toc": {
        "move_down": "j",
        "move_up": "k",
        "collapse_or_parent": "h",
        "expand_or_child": "l",
        "open": "<CR>",
        "close": "<Esc>",
        "help_toggle": "?",
        "expand_all": "<leader>xar",
        "toggle_selected": "<leader>xr",
        "collapse_all": "<leader>xc"
      },
      "vault": {
        "move_down": "j",
        "move_up": "k",
        "up": "h",
        "enter_or_open": "l",
        "close": "<Esc>",
        "quit": "<C-q>",
        "copy": "yy",
        "cut": "dd",
        "paste": "p",
        "new_entry": "<leader>n",
        "rename": "<leader>rn",
        "deploy_sync": "<C-d>",
        "toggle_theme": "<leader>m"
      },
      "help": {
        "scroll_down": "j",
        "scroll_up": "k",
        "close": "?"
      }
    }
  }
}
```

The repository ships a ready-to-edit template at `template_config.json`.

Guardrails:

- Leader must be a single printable ASCII character (space is allowed).
- Only Vim-style tokens are accepted (`j`, `gg`, `<C-s>`, `<Esc>`, `<CR>`, etc.).
- Each action accepts exactly one key sequence (string value).
- Unknown tokens, non-ASCII keys, and `Ctrl+Alt` combos are rejected.
- Keymaps do not apply while typing in vault create/rename inputs.

### Theme assumptions

The GTK UI ships with a dark/light theme toggle (` ,m `). Colors and font sizes
come from `design_constants.py`. The window background uses a translucent
overlay based on the active theme.

### Leader commands

Leader is `,` followed by a short token. Block commands are prefixed with `b`:

- `,bn` normal text
- `,bht` title
- `,bh1` / `,bh2` / `,bh3` headings
- `,bi` index
- `,bjs` Three.js block
- `,bpy` Python render block
- `,bltx` LaTeX block
- `,bmap` map block
- `,i` open the index drill
- `,v` open vault mode
- `,m` toggle light/dark mode

### Bash completion

The installer drops a completion script into
`${XDG_CONFIG_HOME:-~/.config}/bash_completion.d/gvim` and adds a loader to
`~/.bashrc` if needed.

---

## Vaults

Vaults are registered directories stored in your config. Use `gvim init` to
register the current directory. Press `,v` to open vault mode, navigate with
`h/j/k/l`, and press `Escape` to return to document mode. In vault mode, press
`,n` to create a new `.gvim` file (with extension) or a new folder (no
extension). If you launch without a file and have vaults configured, the app
opens in vault mode. In vault mode, `yy` copies, `dd` cuts, and `p` pastes into
the current folder.

## Notes

- Blocks are separate; there is no inline mixing.
- Vim runs externally in your terminal; GTK stays focused on layout.
- Documents are stored as text `.gvim` files suitable for Git diffing.
- 3D blocks store their JS source inside the `.gvim` file.
- Python render blocks execute via a configured Python path and must write to `__gvim__.renderer`.
- Python render output is rendered at runtime (not embedded).
- LaTeX blocks render via KaTeX in a WebKit view with local assets.
- Image blocks are not supported in the text `.gvim` format.
- HTML export uses CDN assets for Three.js and KaTeX, embeds Python renders as base64 SVG, and adds a light/dark toggle in the top-right.
- Map blocks render GeoJSON via Leaflet with theme-aware tiles.

---

## Rendering blocks

### Three.js blocks

Insert a block with `,bjs` and write module JS. The runtime provides `THREE`,
`scene`, `camera`, `renderer`, and `canvas` as globals.

Scope and expectations:

- The app ships only the core `three.module.min.js` build (no examples or loaders).
- There is no build pipeline; your code is executed as an ES module at runtime.
- If you need loaders (GLTFLoader, etc.), you must import them yourself (CDN or local).
- The WebKit view uses a transparent canvas at a fixed 300px height.

```js
const geometry = new THREE.BoxGeometry(1, 1, 1);
const material = new THREE.MeshStandardMaterial({ color: 0xaaaaaa });
const cube = new THREE.Mesh(geometry, material);
scene.add(cube);
camera.position.z = 3;

const light = new THREE.DirectionalLight(0xffffff, 1);
light.position.set(2, 3, 4);
scene.add(light);

function animate() {
  requestAnimationFrame(animate);
  cube.rotation.x += 0.01;
  cube.rotation.y += 0.015;
  renderer.render(scene, camera);
}
animate();
```

### Python render blocks

Insert a block with `,bpy`. Configure the Python path on first launch. Your
code runs in a small helper runtime and must write an SVG to
`__gvim__.renderer`. The runtime injects helpers and defaults that make quick
plots easy.

Runtime surface:

- `__gvim__.renderer` — absolute output path for the SVG.
- `__gvim__.format` — currently always `"svg"`.
- `plot_coord(*coords, title=None)` — plot a list of `(x, y)` points.
- `plot_func(x, *y_funcs, title=None, **named_y)` — plot one or more series
  from sequences or callables; named series are rendered in sorted key order.

Plot defaults applied by the renderer:

- Matplotlib rcParams set text/axes/tick colors to the active UI theme.
- Figure and axes backgrounds are transparent.
- `plot_func` draws x/y axes at 0 and enables a grid.
- Output is forced to SVG; black fills/strokes are replaced with theme text
  color to stay readable on dark backgrounds.

Examples:

```python
plot_coord((0, 0), (1, 2), (2, 1), title="Points")
```

```python
import numpy as np

x = np.linspace(-5, 5, 100)
plot_func(
    x,
    lambda x: 0.5 * x + 1,
    y2=lambda x: 0.3 * x + 2,
    title="My Plot",
)
```

### LaTeX blocks

Insert a block with `,bltx` and write raw LaTeX. KaTeX renders it via WebKit.

```
\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}
```

### Map blocks

Insert a block with `,bmap` and write Leaflet JS. The runtime provides `L`,
`map`, and `tileLayer` globals.

```js
const points = [
  [40.7484, -73.9857],
  [51.5072, -0.1276],
  [48.8566, 2.3522],
];

points.forEach(([lat, lon]) => {
  L.circleMarker([lat, lon], {
    radius: 5,
    color: "#d0d0d0",
    fillColor: "#d0d0d0",
    fillOpacity: 0.9,
  }).addTo(map);
});

map.fitBounds(L.latLngBounds(points).pad(0.2));
```

### `.gvim` text format

Blocks are stored as plain text with block headers (SQLite is no longer used):

```
# GVIM v1
::text
kind: body
My notes...

::three
<three.js module JS>

::pyimage
format: svg
<python source>

::latex
\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}

::map
// Leaflet globals: L, map, tileLayer
```

### HTML export

Export all `.gvim` documents under the current vault:

```bash
gvim -e
```

This generates an `index.html` at the vault root that lists the exported site
tree.

- Three.js and KaTeX load from CDN to keep the HTML lean.
- Python renders are executed on export and embedded as base64 SVG.
- The exported page supports `j/k` scrolling and a light/dark toggle.

---

## Releases

Tag the repository with the desired semantic version and push:

```bash
git tag v0.4.0
git push origin v0.4.0
```

GitHub Actions builds a source bundle (`gvim-linux-x64.tar.gz`), updates
`_version.py`, and publishes the asset alongside the tagged release.
