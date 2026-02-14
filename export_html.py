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
    dark = colors_for("dark")
    light = colors_for("light")
    blocks_html = []
    latex_sources = []
    map_sources = []
    toc_text, heading_ids = _build_toc(document)
    for index, block in enumerate(document.blocks):
        if isinstance(block, TextBlock):
            blocks_html.append(
                _render_text_block(block, toc_text, heading_ids, index)
            )
        elif isinstance(block, ThreeBlock):
            blocks_html.append(_render_three_block(block.source, index))
        elif isinstance(block, PythonImageBlock):
            blocks_html.append(
                _render_pyimage_block(block, python_path, ui_mode)
            )
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
        f"<html data-theme=\"{ui_mode}\">\n"
        "  <head>\n"
        '    <meta charset="utf-8" />\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f'    <link rel="stylesheet" href="{KATEX_CSS_CDN}" />\n'
        f'    <link rel="stylesheet" href="{LEAFLET_CSS_CDN}" />\n'
        "    <style>\n"
        "      :root {\n"
        "        color-scheme: light dark;\n"
        "      }\n"
        "      :root[data-theme=\"dark\"] {\n"
        f"        --body-background: {dark.export_body_background};\n"
        f"        --body-text: {dark.export_body_text};\n"
        f"        --title-color: {dark.export_title};\n"
        f"        --h1-color: {dark.export_h1};\n"
        f"        --h2-color: {dark.export_h2};\n"
        f"        --h3-color: {dark.export_h3};\n"
        f"        --body-color: {dark.export_body};\n"
        f"        --toc-color: {dark.export_toc};\n"
        f"        --latex-color: {dark.export_latex};\n"
        f"        --toggle-bg: {dark.export_toggle_bg};\n"
        f"        --toggle-text: {dark.export_toggle_text};\n"
        f"        --toggle-border: {dark.export_toggle_border};\n"
        f"        --toggle-active-bg: {dark.export_toggle_active_bg};\n"
        f"        --toggle-active-text: {dark.export_toggle_active_text};\n"
        "      }\n"
        "      :root[data-theme=\"light\"] {\n"
        f"        --body-background: {light.export_body_background};\n"
        f"        --body-text: {light.export_body_text};\n"
        f"        --title-color: {light.export_title};\n"
        f"        --h1-color: {light.export_h1};\n"
        f"        --h2-color: {light.export_h2};\n"
        f"        --h3-color: {light.export_h3};\n"
        f"        --body-color: {light.export_body};\n"
        f"        --toc-color: {light.export_toc};\n"
        f"        --latex-color: {light.export_latex};\n"
        f"        --toggle-bg: {light.export_toggle_bg};\n"
        f"        --toggle-text: {light.export_toggle_text};\n"
        f"        --toggle-border: {light.export_toggle_border};\n"
        f"        --toggle-active-bg: {light.export_toggle_active_bg};\n"
        f"        --toggle-active-text: {light.export_toggle_active_text};\n"
        "      }\n"
        "      body {\n"
        "        margin: 0;\n"
        "        background: var(--body-background);\n"
        "        color: var(--body-text);\n"
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
        f"      .block-title {{ font-size: {font.export_title}; font-weight: 600; color: var(--title-color); }}\n"
        f"      .block-h1 {{ font-size: {font.export_h1}; font-weight: 600; color: var(--h1-color); }}\n"
        f"      .block-h2 {{ font-size: {font.export_h2}; font-weight: 600; color: var(--h2-color); }}\n"
        f"      .block-h3 {{ font-size: {font.export_h3}; font-weight: 600; color: var(--h3-color); }}\n"
        f"      .block-body {{ font-size: {font.export_body}; line-height: 1.6; color: var(--body-color); white-space: pre-wrap; }}\n"
        f"      .block-toc {{ font-size: {font.export_toc}; color: var(--toc-color); white-space: pre-wrap; }}\n"
        "      .block-toc a { color: inherit; text-decoration: none; }\n"
        "      .block-toc a:visited { color: inherit; }\n"
        "      .block-toc a:hover { text-decoration: underline; }\n"
        f"      .toc-index {{ font-size: {font.export_h3}; font-weight: 600; color: var(--h3-color); margin-bottom: 4px; }}\n"
        "      .toc-empty { color: var(--toc-color); }\n"
        "      .toc-line { display: block; line-height: 0.2; margin: 0; }\n"
        "      .toc-line.depth-2 { padding-left: 16px; }\n"
        "      .toc-line.depth-3 { padding-left: 32px; }\n"
        "      .block-pyimage { text-align: center; }\n"
        "      .block-pyimage img { max-width: 100%; height: auto; display: inline-block; }\n"
        "      :root[data-theme=\"dark\"] .block-pyimage img.light { display: none; }\n"
        "      :root[data-theme=\"light\"] .block-pyimage img.dark { display: none; }\n"
        "      .block-three canvas { width: 100%; height: 300px; display: block; }\n"
        f"      .block-latex {{ font-size: {font.export_latex}; color: var(--latex-color); }}\n"
        "      .theme-toggle {\n"
        "        position: fixed;\n"
        "        top: 16px;\n"
        "        right: 16px;\n"
        "        display: inline-flex;\n"
        "        gap: 6px;\n"
        "        padding: 6px;\n"
        "        border-radius: 999px;\n"
        "        background: var(--toggle-bg);\n"
        "        color: var(--toggle-text);\n"
        "        border: 1px solid var(--toggle-border);\n"
        "        font-size: 12px;\n"
        "        z-index: 10;\n"
        "        backdrop-filter: blur(6px);\n"
        "      }\n"
        "      .theme-toggle button {\n"
        "        border: none;\n"
        "        background: transparent;\n"
        "        color: inherit;\n"
        "        padding: 4px 10px;\n"
        "        border-radius: 999px;\n"
        "        font: inherit;\n"
        "        cursor: pointer;\n"
        "      }\n"
        "      .theme-toggle button.active {\n"
        "        background: var(--toggle-active-bg);\n"
        "        color: var(--toggle-active-text);\n"
        "      }\n"
        "      .block-map { height: 320px; }\n"
        "      .block-map > div { height: 100%; }\n"
        "    </style>\n"
        "  </head>\n"
        "  <body>\n"
        "    <div class=\"theme-toggle\" role=\"group\" aria-label=\"Theme toggle\">\n"
        "      <button type=\"button\" data-theme=\"dark\">Dark</button>\n"
        "      <button type=\"button\" data-theme=\"light\">Light</button>\n"
        "    </div>\n"
        "    <main>\n"
        f"{blocks_joined}\n"
        "    </main>\n"
        f'    <script src="{KATEX_JS_CDN}"></script>\n'
        f'    <script src="{LEAFLET_JS_CDN}"></script>\n'
        "    <script>\n"
        f"      const themeDefault = '{ui_mode}';\n"
        "      const themeStorageKey = 'gtkv-theme';\n"
        "      const root = document.documentElement;\n"
        "      const toggleButtons = document.querySelectorAll('.theme-toggle button');\n"
        "      const getStoredTheme = () => {\n"
        "        try { return localStorage.getItem(themeStorageKey); } catch (err) { return null; }\n"
        "      };\n"
        "      const setStoredTheme = (value) => {\n"
        "        try { localStorage.setItem(themeStorageKey, value); } catch (err) {}\n"
        "      };\n"
        "      const applyTheme = (value) => {\n"
        "        root.dataset.theme = value;\n"
        "        toggleButtons.forEach((btn) => {\n"
        "          btn.classList.toggle('active', btn.dataset.theme === value);\n"
        "        });\n"
        "      };\n"
        "      const preferredTheme = getStoredTheme() || themeDefault;\n"
        "      applyTheme(preferredTheme);\n"
        "      const latexBlocks = [];\n"
        f"{latex_items}"
        "      const mapBlocks = [];\n"
        f"{map_items}"
        f"      const mapTiles = {{ dark: '{dark.map_tile_url}', light: '{light.map_tile_url}' }};\n"
        f"      const mapAttrs = {{ dark: '{dark.map_tile_attr}', light: '{light.map_tile_attr}' }};\n"
        "      const mapInstances = [];\n"
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
        "        const tileLayer = L.tileLayer(mapTiles[preferredTheme], { attribution: mapAttrs[preferredTheme] }).addTo(map);\n"
        "        mapInstances.push({ map, tileLayer });\n"
        "        try {\n"
        "          const fn = new Function('L', 'map', 'tileLayer', src);\n"
        "          fn(L, map, tileLayer);\n"
        "        } catch (err) {\n"
        "          el.textContent = String(err);\n"
        "        }\n"
        "      }\n"
        "      const updateMapTiles = (value) => {\n"
        "        mapInstances.forEach((entry) => {\n"
        "          if (entry.tileLayer) entry.tileLayer.remove();\n"
        "          entry.tileLayer = L.tileLayer(mapTiles[value], { attribution: mapAttrs[value] }).addTo(entry.map);\n"
        "        });\n"
        "      };\n"
        "      toggleButtons.forEach((btn) => {\n"
        "        btn.addEventListener('click', () => {\n"
        "          const value = btn.dataset.theme;\n"
        "          applyTheme(value);\n"
        "          updateMapTiles(value);\n"
        "          setStoredTheme(value);\n"
        "        });\n"
        "      });\n"
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


def _render_text_block(
    block: TextBlock, toc_text: str, heading_ids: dict[int, str], index: int
) -> str:
    kind_class = f"block-{block.kind}"
    if block.kind == "toc":
        return f'<section class="block {kind_class}">{toc_text}</section>'
    text_source = block.text
    text = _escape_html(text_source)
    if block.kind in {"h1", "h2", "h3"}:
        anchor = heading_ids.get(index)
        if anchor:
            return f'<section id="{anchor}" class="block {kind_class}">{text}</section>'
    return f'<section class="block {kind_class}">{text}</section>'


def _render_pyimage_block(
    block: PythonImageBlock, python_path: str | None, ui_mode: str
) -> str:
    if python_path:
        dark_result = py_runner.render_python_image(
            block.source, python_path, block.format, ui_mode="dark"
        )
        light_result = py_runner.render_python_image(
            block.source, python_path, block.format, ui_mode="light"
        )
        if not dark_result.rendered_data and not light_result.rendered_data:
            error = _escape_html(
                dark_result.error
                or light_result.error
                or "Python render failed"
            )
            return (
                f'<section class="block block-pyimage">Python render error: {error}</section>'
            )
        dark_encoded = (
            base64.b64encode(dark_result.rendered_data.encode("utf-8")).decode(
                "utf-8"
            )
            if dark_result.rendered_data
            else None
        )
        light_encoded = (
            base64.b64encode(light_result.rendered_data.encode("utf-8")).decode(
                "utf-8"
            )
            if light_result.rendered_data
            else None
        )
        dark_img = (
            f'<img class="pyimage dark" src="data:image/svg+xml;base64,{dark_encoded}" />'
            if dark_encoded
            else ""
        )
        light_img = (
            f'<img class="pyimage light" src="data:image/svg+xml;base64,{light_encoded}" />'
            if light_encoded
            else ""
        )
        return f'<section class="block block-pyimage">{dark_img}{light_img}</section>'
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


def _build_toc(document: BlockDocument) -> tuple[str, dict[int, str]]:
    headings: list[tuple[int, str, str]] = []
    heading_ids: dict[int, str] = {}
    seen: dict[str, int] = {}
    for index, block in enumerate(document.blocks):
        if isinstance(block, TextBlock) and block.kind in {"h1", "h2", "h3"}:
            text = block.text.strip().splitlines()[0] if block.text.strip() else ""
            if not text:
                continue
            anchor = _slugify_heading(text)
            count = seen.get(anchor, 0) + 1
            seen[anchor] = count
            if count > 1:
                anchor = f"{anchor}-{count}"
            heading_ids[index] = anchor
            headings.append((index, block.kind, text))

    if not headings:
        return (
            "<div class=\"toc-index\">Index</div>"
            "<div class=\"toc-empty\">(No headings yet)</div>",
            heading_ids,
        )

    lines = ["<div class=\"toc-index\">Index</div>"]
    for index, kind, text in headings:
        anchor = heading_ids.get(index)
        if not anchor:
            continue
        anchor_link = f"- <a href=\"#{anchor}\">{_escape_html(text)}</a>"
        if kind == "h1":
            lines.append(f"<div class=\"toc-line depth-1\">{anchor_link}</div>")
        elif kind == "h2":
            lines.append(f"<div class=\"toc-line depth-2\">{anchor_link}</div>")
        else:
            lines.append(f"<div class=\"toc-line depth-3\">{anchor_link}</div>")
    return "\n".join(lines), heading_ids


def _slugify_heading(text: str) -> str:
    slug = []
    prev_dash = False
    for char in text.strip().lower():
        if char.isalnum():
            slug.append(char)
            prev_dash = False
        elif not prev_dash:
            slug.append("-")
            prev_dash = True
    slug_text = "".join(slug).strip("-")
    return slug_text or "section"
