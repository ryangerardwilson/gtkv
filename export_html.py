"""HTML export for .docv documents."""

from __future__ import annotations

import base64
from pathlib import Path

import py_runner
from design_constants import colors_for, font
from block_model import (
    BlockDocument,
    LatexBlock,
    MapBlock,
    PythonImageBlock,
    TextBlock,
    ThreeBlock,
)


KATEX_CSS_CDN = "https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css"
KATEX_JS_CDN = "https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"
THREE_JS_CDN = "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.min.js"
LEAFLET_CSS_CDN = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
LEAFLET_JS_CDN = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"


def export_document(
    document: BlockDocument,
    output_path: Path,
    python_path: str | None,
    ui_mode: str = "dark",
) -> None:
    html = _build_html(document, python_path, ui_mode)
    output_path.write_text(html, encoding="utf-8")


def _build_html(
    document: BlockDocument, python_path: str | None, ui_mode: str
) -> str:
    palette = colors_for(ui_mode)
    blocks_html = []
    latex_sources = []
    map_sources = []
    toc_text = _build_toc(document)
    for index, block in enumerate(document.blocks):
        if isinstance(block, TextBlock):
            blocks_html.append(_render_text_block(block, toc_text))
        elif isinstance(block, ThreeBlock):
            blocks_html.append(_render_three_block(block.source, index))
        elif isinstance(block, PythonImageBlock):
            blocks_html.append(_render_pyimage_block(block, python_path))
        elif isinstance(block, LatexBlock):
            block_id = f"latex-{len(latex_sources)}"
            latex_sources.append((block_id, block.source))
            blocks_html.append(f'<div class="block block-latex" id="{block_id}"></div>')
        elif isinstance(block, MapBlock):
            block_id = f"map-{len(map_sources)}"
            map_sources.append((block_id, block.source))
            blocks_html.append(f'<div class="block block-map" id="{block_id}"></div>')

    blocks_joined = "".join(blocks_html)
    latex_items = "".join(
        f"      latexBlocks.push([{_js_string(block_id)}, {_js_string(source)}]);\n"
        for block_id, source in latex_sources
    )
    map_items = "".join(
        f"      mapBlocks.push([{_js_string(block_id)}, {_js_string(source)}]);\n"
        for block_id, source in map_sources
    )
    return (
        "<!doctype html>\n"
        "<html>\n"
        "  <head>\n"
        '    <meta charset="utf-8" />\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f'    <link rel="stylesheet" href="{KATEX_CSS_CDN}" />\n'
        f'    <link rel="stylesheet" href="{LEAFLET_CSS_CDN}" />\n'
        "    <style>\n"
        "      :root {\n"
        f"        color-scheme: {ui_mode};\n"
        "      }\n"
        "      body {\n"
        "        margin: 0;\n"
        f"        background: {palette.export_body_background};\n"
        f"        color: {palette.export_body_text};\n"
        "        font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;\n"
        "      }\n"
        "      main {\n"
        "        max-width: 960px;\n"
        "        margin: 32px auto;\n"
        "        padding: 0 24px 80px;\n"
        "      }\n"
        "      .block {\n"
        "        padding: 16px 20px;\n"
        "        margin: 0;\n"
        "      }\n"
        f"      .block-title {{ font-size: {font.export_title}; font-weight: 600; color: {palette.export_title}; }}\n"
        f"      .block-h1 {{ font-size: {font.export_h1}; font-weight: 600; color: {palette.export_h1}; }}\n"
        f"      .block-h2 {{ font-size: {font.export_h2}; font-weight: 600; color: {palette.export_h2}; }}\n"
        f"      .block-h3 {{ font-size: {font.export_h3}; font-weight: 600; color: {palette.export_h3}; }}\n"
        f"      .block-body {{ font-size: {font.export_body}; line-height: 1.6; color: {palette.export_body}; white-space: pre-wrap; }}\n"
        f"      .block-toc {{ font-size: {font.export_toc}; color: {palette.export_toc}; white-space: pre-wrap; }}\n"
        "      .block-pyimage { text-align: center; }\n"
        "      .block-pyimage img { max-width: 100%; height: auto; display: inline-block; }\n"
        "      .block-three canvas { width: 100%; height: 300px; display: block; }\n"
        f"      .block-latex {{ font-size: {font.export_latex}; color: {palette.export_latex}; }}\n"
        "      .block-map { height: 320px; }\n"
        "      .block-map > div { height: 100%; }\n"
        "    </style>\n"
        "  </head>\n"
        "  <body>\n"
        "    <main>\n"
        f"{blocks_joined}\n"
        "    </main>\n"
        f'    <script src="{KATEX_JS_CDN}"></script>\n'
        f'    <script src="{LEAFLET_JS_CDN}"></script>\n'
        "    <script>\n"
        "      const latexBlocks = [];\n"
        f"{latex_items}"
        "      const mapBlocks = [];\n"
        f"{map_items}"
        "      for (const [id, src] of latexBlocks) {\n"
        "        const el = document.getElementById(id);\n"
        "        if (!el) continue;\n"
        "        try { katex.render(src, el, { throwOnError: false, displayMode: true }); }\n"
        "        catch (err) { el.textContent = String(err); }\n"
        "      }\n"
        "      for (const [id, src] of mapBlocks) {\n"
        "        const el = document.getElementById(id);\n"
        "        if (!el) continue;\n"
        "        const map = L.map(el, { zoomControl: false, attributionControl: true });\n"
        f"        const tileLayer = L.tileLayer('{palette.map_tile_url}', {{ attribution: '{palette.map_tile_attr}' }}).addTo(map);\n"
        "        try {\n"
        "          const fn = new Function('L', 'map', 'tileLayer', src);\n"
        "          fn(L, map, tileLayer);\n"
        "        } catch (err) {\n"
        "          el.textContent = String(err);\n"
        "        }\n"
        "      }\n"
        "      document.addEventListener('keydown', (event) => {\n"
        "        if (event.target && event.target.tagName === 'INPUT') return;\n"
        "        if (event.key === 'j') {\n"
        "          window.scrollBy({ top: 80, left: 0, behavior: 'smooth' });\n"
        "        } else if (event.key === 'k') {\n"
        "          window.scrollBy({ top: -80, left: 0, behavior: 'smooth' });\n"
        "        }\n"
        "      });\n"
        "    </script>\n"
        "  </body>\n"
        "</html>\n"
    )


def _render_text_block(block: TextBlock, toc_text: str) -> str:
    kind_class = f"block-{block.kind}"
    text_source = toc_text if block.kind == "toc" else block.text
    text = _escape_html(text_source)
    return f'<section class="block {kind_class}">{text}</section>'


def _render_pyimage_block(block: PythonImageBlock, python_path: str | None) -> str:
    if python_path:
        result = py_runner.render_python_image(block.source, python_path, block.format)
        if result.rendered_data and not result.error:
            encoded = base64.b64encode(result.rendered_data.encode("utf-8")).decode(
                "utf-8"
            )
            src = f"data:image/svg+xml;base64,{encoded}"
            return f'<section class="block block-pyimage"><img src="{src}" /></section>'
        error = _escape_html(result.error or "Render failed")
        return f'<section class="block block-pyimage">Python render error: {error}</section>'
    return '<section class="block block-pyimage">Python path not configured.</section>'


def _render_three_block(source: str, index: int) -> str:
    module_source = _escape_js(source)
    canvas_id = f"gtkv-three-{index}"
    return (
        '<section class="block block-three">'
        f'<canvas id="{canvas_id}"></canvas>'
        '<script type="module">'
        f"import * as THREE from '{THREE_JS_CDN}';"
        f"const canvas = document.getElementById('{canvas_id}');"
        "const scene = new THREE.Scene();"
        "const camera = new THREE.PerspectiveCamera(60, canvas.clientWidth / 300, 0.1, 1000);"
        "const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, canvas });"
        "renderer.setClearColor(0x000000, 0);"
        "renderer.setPixelRatio(devicePixelRatio || 1);"
        "const resize = () => {"
        "  const width = canvas.clientWidth;"
        "  const height = 300;"
        "  renderer.setSize(width, height);"
        "  camera.aspect = width / height;"
        "  camera.updateProjectionMatrix();"
        "};"
        "resize();"
        "window.addEventListener('resize', resize);"
        "Object.assign(window, { THREE, scene, camera, renderer, canvas });"
        f"{module_source}"
        "</script>"
        "</section>"
    )


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_js(text: str) -> str:
    return text.replace("</script>", "<\\/script>")


def _js_string(value: str) -> str:
    return (
        '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    )


def _build_toc(document: BlockDocument) -> str:
    headings = []
    for block in document.blocks:
        if isinstance(block, TextBlock) and block.kind in {"h1", "h2", "h3"}:
            text = block.text.strip().splitlines()[0] if block.text.strip() else ""
            if text:
                headings.append((block.kind, text))

    if not headings:
        return "Table of Contents\n\n(No headings yet)"

    lines = ["Table of Contents", ""]
    for kind, text in headings:
        indent = ""
        if kind == "h2":
            indent = "  "
        elif kind == "h3":
            indent = "    "
        lines.append(f"{indent}- {text}")
    return "\n".join(lines)
