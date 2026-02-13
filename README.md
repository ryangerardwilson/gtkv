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
- Optional: the `o` file picker for save path selection.
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

- `gtkv` — start the editor.
- `gtkv doc.docv` — open an existing document.
- `,p` — insert a paragraph block.
- `,ht` — insert a title block.
- `,h1` / `,h2` / `,h3` — insert heading blocks.
- `,toc` — insert a table of contents block.
- `,js` — insert a 3D block and edit its Three.js module JS in Vim.
- `,py` — insert a Python render block (SVG output).
- `,ltx` — insert a LaTeX block rendered with KaTeX.
- `j/k` — move between blocks.
- `Enter` — open the selected text or code block in Vim.
- Exit Vim — refreshes the block content in GTK.
- `Ctrl+S` — save the current document (prompts for a path on first save).
- `-v` — print installed version.
- `-u` — upgrade to the latest release.
- `-e output.html doc.docv` — export a document to HTML.
- `-h` — show CLI help.

### Leader commands

Leader is `,` followed by a short token:

- `,p` paragraph
- `,ht` title
- `,h1` / `,h2` / `,h3` headings
- `,toc` table of contents
- `,js` Three.js block
- `,py` Python render block
- `,ltx` LaTeX block

### Bash completion

The installer drops a completion script into
`${XDG_CONFIG_HOME:-~/.config}/bash_completion.d/gtkv` and adds a loader to
`~/.bashrc` if needed.

---

## Notes

- Blocks are separate; there is no inline mixing.
- Vim runs externally in your terminal; GTK stays focused on layout.
- Documents are stored as text `.docv` files suitable for Git diffing.
- 3D blocks store their JS source inside the `.docv` file.
- Python render blocks execute via a configured Python path and must write to `__gtkv__.renderer`.
- Python render output is rendered at runtime (not embedded).
- LaTeX blocks render via KaTeX in a WebKit view with local assets.
- Image blocks are not supported in the text `.docv` format.
- HTML export uses CDN assets for Three.js and KaTeX, and embeds Python renders as base64 SVG.

---

## Rendering blocks

### Three.js blocks

Insert a block with `,js` and write module JS. The runtime provides `THREE`,
`scene`, `camera`, `renderer`, and `canvas` as globals.

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

Insert a block with `,py`. Configure the Python path on first launch. Your code
must write an SVG to `__gtkv__.renderer`.

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.plot([0, 1, 2], [0, 1, 0.5])
fig.savefig(__gtkv__.renderer, format="svg", dpi=200, transparent=True, bbox_inches="tight")
```

### LaTeX blocks

Insert a block with `,ltx` and write raw LaTeX. KaTeX renders it via WebKit.

```
\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}
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
```

### HTML export

Export a document to a self-contained HTML page with a dark theme:

```bash
gtkv -e output.html doc.docv
```

- Three.js and KaTeX load from CDN to keep the HTML lean.
- Python renders are executed on export and embedded as base64 SVG.
- The exported page supports `j/k` scrolling.

---

## Releases

Tag the repository with the desired semantic version and push:

```bash
git tag v0.4.0
git push origin v0.4.0
```

GitHub Actions builds a source bundle (`gtkv-linux-x64.tar.gz`), updates
`_version.py`, and publishes the asset alongside the tagged release.
