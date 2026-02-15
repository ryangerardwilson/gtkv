# gtkv

`gtkv` is a GTK4 block-based editor that keeps Vim as the editor. Text and code
live in separate blocks, and text blocks open in an external terminal Vim
session for full editing power. Documents are stored as a git-friendly text
`.docv` file. 3D and LaTeX blocks render with WebKitGTK.

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

- `gtkv` — open a new document.
- `gtkv doc.docv` — open an existing document.
- `gtkv init` — initialize a vault in the current directory.
- `,bn` — insert a normal text block.
- `,bht` — insert a title block.
- `,bh1` / `,bh2` / `,bh3` — insert heading blocks.
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
- `Enter` — open the selected text or code block in Vim.
- `Enter` on a TOC block — open the outline drill.
- Exit Vim — refreshes the block content in GTK.
- `Ctrl+S` — save the current document.
- `Ctrl+E` — export HTML alongside the document.
- `Ctrl+T` — save and exit.
- `q` / `Ctrl+X` — exit without saving.
- `Escape` — return to document mode from vault mode.
- `-v` — print installed version.
- `-u` — upgrade to the latest release.
- `-e [output.html] doc.docv` — export to HTML (defaults to same basename).
- `-e` — export all `.docv` recursively from project root (requires `__init__.docv`).
- `-q` — quickstart a new document with demo content.
- `-h` — show CLI help.

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
`${XDG_CONFIG_HOME:-~/.config}/bash_completion.d/gtkv` and adds a loader to
`~/.bashrc` if needed.

---

## Vaults

Use `gtkv init` to create a vault anchor (`__init__.docv`) and register the
current directory. Press `,v` to open vault mode, navigate with `h/j/k/l`, and
press `Escape` to return to document mode. In vault mode, press `,n` to create
a new `.docv` file (with extension) or a new folder (no extension). If all
registered vaults have no `.docv` files, the app opens in vault mode.
In vault mode, `yy` copies, `dd` cuts, and `p` pastes into the current folder.

## Notes

- Blocks are separate; there is no inline mixing.
- Vim runs externally in your terminal; GTK stays focused on layout.
- Documents are stored as text `.docv` files suitable for Git diffing.
- 3D blocks store their JS source inside the `.docv` file.
- Python render blocks execute via a configured Python path and must write to `__gtkv__.renderer`.
- Python render output is rendered at runtime (not embedded).
- LaTeX blocks render via KaTeX in a WebKit view with local assets.
- Image blocks are not supported in the text `.docv` format.
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
code must write an SVG to `__gtkv__.renderer`.

Defaults applied by the renderer to match the active UI mode:

- Matplotlib rcParams set text/axes/tick colors to `#d0d0d0`.
- Figure and axes backgrounds are transparent.
- Saved SVGs are post-processed to replace black fills/strokes with `#d0d0d0`.

If you override colors, prefer light tones so plots stay readable on dark
backgrounds.

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.plot([0, 1, 2], [0, 1, 0.5])
fig.savefig(__gtkv__.renderer, format="svg", dpi=200, transparent=True, bbox_inches="tight")
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

### `.docv` text format

Blocks are stored as plain text with block headers (SQLite is no longer used):

```
# GTKV v2
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

Export a document to a self-contained HTML page (toggleable light/dark):

```bash
gtkv -e [output.html] doc.docv
```

Export all `.docv` documents under a project root (requires `__init__.docv` in that root):

```bash
gtkv -e
```

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

GitHub Actions builds a source bundle (`gtkv-linux-x64.tar.gz`), updates
`_version.py`, and publishes the asset alongside the tagged release.
