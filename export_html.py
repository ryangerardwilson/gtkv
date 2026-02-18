"""HTML export for .gvim documents."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

import py_runner
from design_constants import colors_for, font
from block_model import (
    BlockDocument,
    LatexBlock,
    MapBlock,
    PythonImageBlock,
    TextBlock,
    ThreeBlock,
    build_heading_numbering,
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
    index_tree_html: str | None = None,
    index_href: str | None = None,
) -> None:
    html = _build_html(document, python_path, ui_mode, index_tree_html, index_href)
    output_path.write_text(html, encoding="utf-8")


def _normalize_index_items(
    root: Path,
    items: list[tuple[Path, str | None]],
) -> list[tuple[Path, str]]:
    rel_items: list[tuple[Path, str]] = []
    for path, doc_title in items:
        rel_path = path.relative_to(root)
        rel_items.append((rel_path, doc_title or rel_path.stem or rel_path.name))
    return rel_items


def export_vault_index(
    root: Path,
    items: list[tuple[Path, str | None]],
    ui_mode: str = "dark",
    title: str | None = None,
) -> None:
    rel_items = _normalize_index_items(root, items)
    index_title = title or "Index"
    html = _build_index_html(rel_items, ui_mode, index_title)
    (root / "index.html").write_text(html, encoding="utf-8")


def build_index_tree_html(
    rel_items: list[tuple[Path, str]],
    base_prefix: str = "",
) -> str:
    return _build_index_tree_html(rel_items, base_prefix)


def build_index_link_id(rel_path: Path) -> str:
    return _index_link_id(rel_path)


def _build_html(
    document: BlockDocument,
    python_path: str | None,
    ui_mode: str,
    index_tree_html: str | None,
    index_href: str | None,
) -> str:
    dark = colors_for("dark")
    light = colors_for("light")
    blocks_html = []
    latex_sources = []
    map_sources = []
    numbering = build_heading_numbering(document.blocks)
    toc_text, heading_ids = _build_toc(document, numbering)
    for index, block in enumerate(document.blocks):
        if isinstance(block, TextBlock):
            blocks_html.append(
                _render_text_block(block, toc_text, heading_ids, numbering, index)
            )
        elif isinstance(block, ThreeBlock):
            blocks_html.append(_render_three_block(block.source, index))
        elif isinstance(block, PythonImageBlock):
            blocks_html.append(_render_pyimage_block(block, python_path, ui_mode))
        elif isinstance(block, LatexBlock):
            block_id = f"latex-{len(latex_sources)}"
            latex_sources.append((block_id, block.source))
            blocks_html.append(f'<div class="block block-latex" id="{block_id}"></div>')
        elif isinstance(block, MapBlock):
            block_id = len(map_sources)
            dark_id = f"map-dark-{block_id}"
            light_id = f"map-light-{block_id}"
            map_sources.append((dark_id, light_id, block.source))
            blocks_html.append(
                '<div class="block block-map">'
                f'<div id="{dark_id}" class="map-pane dark"></div>'
                f'<div id="{light_id}" class="map-pane light"></div>'
                "</div>"
            )

    blocks_joined = "".join(blocks_html)
    latex_items = "".join(
        f"      latexBlocks.push([{_js_string(block_id)}, {_js_string(source)}]);\n"
        for block_id, source in latex_sources
    )
    map_items_dark = "".join(
        f"      mapBlocksDark.push([{_js_string(dark_id)}, {_js_string(_rewrite_map_source(source, dark.map_marker))}]);\n"
        for dark_id, _light_id, source in map_sources
    )
    map_items_light = "".join(
        f"      mapBlocksLight.push([{_js_string(light_id)}, {_js_string(_rewrite_map_source(source, light.map_marker))}]);\n"
        for _dark_id, light_id, source in map_sources
    )
    nav_menu_html = ""
    if index_tree_html:
        nav_menu_html = (
            '    <div class="nav-menu" aria-label="Index menu">\n'
            '      <button type="button" class="nav-button" aria-label="Open index menu">\n'
            "        <span></span>\n"
            "        <span></span>\n"
            "        <span></span>\n"
            "      </button>\n"
            "    </div>\n"
            '    <div class="index-modal" role="dialog" aria-modal="true" aria-hidden="true">\n'
            '      <div class="index-backdrop"></div>\n'
            '      <div class="index-panel">\n'
            '        <div class="index-header">Index</div>\n'
            f'        <div class="index-body" tabindex="0">{index_tree_html}</div>\n'
            "      </div>\n"
            "    </div>\n"
        )
    return (
        "<!doctype html>\n"
        f'<html data-theme="{ui_mode}">\n'
        "  <head>\n"
        '    <meta charset="utf-8" />\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f'    <link rel="stylesheet" href="{KATEX_CSS_CDN}" />\n'
        f'    <link rel="stylesheet" href="{LEAFLET_CSS_CDN}" />\n'
        "    <style>\n"
        "      :root {\n"
        "        color-scheme: light dark;\n"
        "      }\n"
        '      :root[data-theme="dark"] {\n'
        f"        --body-background: {dark.export_body_background};\n"
        f"        --body-text: {dark.export_body_text};\n"
        f"        --title-color: {dark.export_title};\n"
        f"        --h1-color: {dark.export_h1};\n"
        f"        --h2-color: {dark.export_h2};\n"
        f"        --h3-color: {dark.export_h3};\n"
        f"        --h4-color: {dark.export_h4};\n"
        f"        --h5-color: {dark.export_h5};\n"
        f"        --h6-color: {dark.export_h6};\n"
        f"        --h4-color: {dark.export_h4};\n"
        f"        --h5-color: {dark.export_h5};\n"
        f"        --h6-color: {dark.export_h6};\n"
        f"        --body-color: {dark.export_body};\n"
        f"        --toc-color: {dark.export_toc};\n"
        f"        --latex-color: {dark.export_latex};\n"
        f"        --toggle-bg: {dark.export_toggle_bg};\n"
        f"        --toggle-text: {dark.export_toggle_text};\n"
        f"        --toggle-border: {dark.export_toggle_border};\n"
        f"        --toggle-active-bg: {dark.export_toggle_active_bg};\n"
        f"        --toggle-active-text: {dark.export_toggle_active_text};\n"
        "      }\n"
        '      :root[data-theme="light"] {\n'
        f"        --body-background: {light.export_body_background};\n"
        f"        --body-text: {light.export_body_text};\n"
        f"        --title-color: {light.export_title};\n"
        f"        --h1-color: {light.export_h1};\n"
        f"        --h2-color: {light.export_h2};\n"
        f"        --h3-color: {light.export_h3};\n"
        f"        --h4-color: {light.export_h4};\n"
        f"        --h5-color: {light.export_h5};\n"
        f"        --h6-color: {light.export_h6};\n"
        f"        --h4-color: {light.export_h4};\n"
        f"        --h5-color: {light.export_h5};\n"
        f"        --h6-color: {light.export_h6};\n"
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
        "        padding: 24px 24px 80px;\n"
        "      }\n"
        "      .block {\n"
        "        padding: 16px 20px;\n"
        "        margin: 0;\n"
        "      }\n"
        f"      .block-title {{ font-size: {font.export_title}; font-weight: 600; color: var(--title-color); }}\n"
        f"      .block-h1 {{ font-size: {font.export_h1}; font-weight: 600; color: var(--h1-color); }}\n"
        f"      .block-h2 {{ font-size: {font.export_h2}; font-weight: 600; color: var(--h2-color); }}\n"
        f"      .block-h3 {{ font-size: {font.export_h3}; font-weight: 600; color: var(--h3-color); }}\n"
        f"      .block-h4 {{ font-size: {font.export_h4}; font-weight: 600; color: var(--h4-color); }}\n"
        f"      .block-h5 {{ font-size: {font.export_h5}; font-weight: 600; color: var(--h5-color); }}\n"
        f"      .block-h6 {{ font-size: {font.export_h6}; font-weight: 600; color: var(--h6-color); }}\n"
        f"      .block-h4 {{ font-size: {font.export_h4}; font-weight: 600; color: var(--h4-color); }}\n"
        f"      .block-h5 {{ font-size: {font.export_h5}; font-weight: 600; color: var(--h5-color); }}\n"
        f"      .block-h6 {{ font-size: {font.export_h6}; font-weight: 600; color: var(--h6-color); }}\n"
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
        "      .toc-line.depth-4 { padding-left: 48px; }\n"
        "      .toc-line.depth-5 { padding-left: 64px; }\n"
        "      .toc-line.depth-6 { padding-left: 80px; }\n"
        "      .toc-line.depth-4 { padding-left: 48px; }\n"
        "      .toc-line.depth-5 { padding-left: 64px; }\n"
        "      .toc-line.depth-6 { padding-left: 80px; }\n"
        "      .block-pyimage { text-align: center; }\n"
        "      .block-pyimage img { max-width: 100%; height: auto; display: inline-block; }\n"
        '      :root[data-theme="dark"] .block-pyimage img.light { display: none; }\n'
        '      :root[data-theme="light"] .block-pyimage img.dark { display: none; }\n'
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
        "      .nav-menu {\n"
        "        position: fixed;\n"
        "        top: 16px;\n"
        "        left: 16px;\n"
        "        z-index: 10;\n"
        "      }\n"
        "      .nav-button {\n"
        "        width: 36px;\n"
        "        height: 32px;\n"
        "        border-radius: 10px;\n"
        "        border: 1px solid var(--toggle-border);\n"
        "        background: var(--toggle-bg);\n"
        "        color: var(--toggle-text);\n"
        "        display: inline-flex;\n"
        "        align-items: center;\n"
        "        justify-content: center;\n"
        "        cursor: pointer;\n"
        "        gap: 4px;\n"
        "      }\n"
        "      .nav-button span {\n"
        "        display: block;\n"
        "        width: 14px;\n"
        "        height: 2px;\n"
        "        background: currentColor;\n"
        "        border-radius: 999px;\n"
        "      }\n"
        "      .index-modal {\n"
        "        position: fixed;\n"
        "        inset: 0;\n"
        "        display: none;\n"
        "        align-items: center;\n"
        "        justify-content: center;\n"
        "        z-index: 20;\n"
        "      }\n"
        "      .index-modal.open {\n"
        "        display: flex;\n"
        "      }\n"
        "      .index-backdrop {\n"
        "        position: absolute;\n"
        "        inset: 0;\n"
        "        background: rgba(0, 0, 0, 0.55);\n"
        "      }\n"
        "      .index-panel {\n"
        "        position: relative;\n"
        "        width: min(720px, 92vw);\n"
        "        max-height: 80vh;\n"
        "        background: var(--body-background);\n"
        "        border: 1px solid var(--toggle-border);\n"
        "        border-radius: 16px;\n"
        "        box-shadow: 0 22px 60px rgba(0, 0, 0, 0.28);\n"
        "        overflow: hidden;\n"
        "        display: flex;\n"
        "        flex-direction: column;\n"
        "      }\n"
        "      .index-header {\n"
        "        padding: 14px 18px;\n"
        "        font-size: 14px;\n"
        "        font-weight: 600;\n"
        "        color: var(--title-color);\n"
        "        border-bottom: 1px solid var(--toggle-border);\n"
        "      }\n"
        "      .index-body {\n"
        "        padding: 14px 18px 18px;\n"
        "        overflow: auto;\n"
        "        outline: none;\n"
        "      }\n"
        "      .index-body .index-tree {\n"
        f"        font-size: {font.export_body};\n"
        "        margin: 0;\n"
        "      }\n"
        "      .index-body ul { list-style: none; margin: 0; padding-left: 16px; }\n"
        "      .index-body li { margin: 4px 0; }\n"
        "      .index-body .dir-name { color: var(--muted-color, var(--body-text)); font-weight: 600; }\n"
        "      .index-body a { color: var(--body-text); text-decoration: none; }\n"
        "      .index-body a:hover { color: var(--link-color, var(--body-text)); text-decoration: underline; }\n"
        "      .index-body a:focus { outline: none; }\n"
        "      .index-body a.nav-selected {\n"
        "        text-decoration: underline;\n"
        "        color: var(--link-color, var(--body-text));\n"
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
        "      .block-map .map-pane { width: 100%; height: 100%; }\n"
        '      :root[data-theme="dark"] .block-map .map-pane.light { display: none; }\n'
        '      :root[data-theme="light"] .block-map .map-pane.dark { display: none; }\n'
        "    </style>\n"
        "  </head>\n"
        "  <body>\n"
        f"{nav_menu_html}"
        '    <div class="theme-toggle" role="group" aria-label="Theme toggle">\n'
        '      <button type="button" data-theme="dark">Dark</button>\n'
        '      <button type="button" data-theme="light">Light</button>\n'
        "    </div>\n"
        "    <main>\n"
        f"{blocks_joined}\n"
        "    </main>\n"
        f'    <script src="{KATEX_JS_CDN}"></script>\n'
        f'    <script src="{LEAFLET_JS_CDN}"></script>\n'
        "    <script>\n"
        f"      const themeDefault = '{ui_mode}';\n"
        f"      const indexHref = {_js_string(index_href) if index_href else 'null'};\n"
        "      const indexHash = indexHref && indexHref.includes('#') ? indexHref.split('#')[1] : null;\n"
        "      const themeStorageKey = 'gvim-theme';\n"
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
        "      const mapBlocksDark = [];\n"
        f"{map_items_dark}"
        "      const mapBlocksLight = [];\n"
        f"{map_items_light}"
        "      for (const [id, src] of latexBlocks) {\n"
        "        const el = document.getElementById(id);\n"
        "        if (!el) continue;\n"
        "        try { katex.render(src, el, { throwOnError: false, displayMode: true }); }\n"
        "        catch (err) { el.textContent = String(err); }\n"
        "      }\n"
        "      for (const [id, src] of mapBlocksDark) {\n"
        "        const el = document.getElementById(id);\n"
        "        if (!el) continue;\n"
        "        const map = L.map(el, { zoomControl: false, attributionControl: true });\n"
        f"        const tileLayer = L.tileLayer('{dark.map_tile_url}', {{ attribution: '{dark.map_tile_attr}' }}).addTo(map);\n"
        "        try {\n"
        "          const fn = new Function('L', 'map', 'tileLayer', src);\n"
        "          fn(L, map, tileLayer);\n"
        "        } catch (err) {\n"
        "          el.textContent = String(err);\n"
        "        }\n"
        "      }\n"
        "      for (const [id, src] of mapBlocksLight) {\n"
        "        const el = document.getElementById(id);\n"
        "        if (!el) continue;\n"
        "        const map = L.map(el, { zoomControl: false, attributionControl: true });\n"
        f"        const tileLayer = L.tileLayer('{light.map_tile_url}', {{ attribution: '{light.map_tile_attr}' }}).addTo(map);\n"
        "        try {\n"
        "          const fn = new Function('L', 'map', 'tileLayer', src);\n"
        "          fn(L, map, tileLayer);\n"
        "        } catch (err) {\n"
        "          el.textContent = String(err);\n"
        "        }\n"
        "      }\n"
        "      toggleButtons.forEach((btn) => {\n"
        "        btn.addEventListener('click', () => {\n"
        "          const value = btn.dataset.theme;\n"
        "          applyTheme(value);\n"
        "          setStoredTheme(value);\n"
        "        });\n"
        "      });\n"
        "      const navButton = document.querySelector('.nav-button');\n"
        "      const indexModal = document.querySelector('.index-modal');\n"
        "      const indexBody = document.querySelector('.index-body');\n"
        "      const indexBackdrop = document.querySelector('.index-backdrop');\n"
        "      let indexLinks = [];\n"
        "      let indexSelected = -1;\n"
        "      const refreshIndexLinks = () => {\n"
        "        indexLinks = indexBody ? Array.from(indexBody.querySelectorAll('a')) : [];\n"
        "      };\n"
        "      const selectById = (id) => {\n"
        "        if (!id) return false;\n"
        "        const idx = indexLinks.findIndex((link) => link.id === id);\n"
        "        if (idx < 0) return false;\n"
        "        setSelected(idx);\n"
        "        return true;\n"
        "      };\n"
        "      const setSelected = (next) => {\n"
        "        if (!indexLinks.length) return;\n"
        "        if (indexSelected >= 0 && indexSelected < indexLinks.length) {\n"
        "          indexLinks[indexSelected].classList.remove('nav-selected');\n"
        "        }\n"
        "        indexSelected = Math.max(0, Math.min(next, indexLinks.length - 1));\n"
        "        const link = indexLinks[indexSelected];\n"
        "        link.classList.add('nav-selected');\n"
        "        link.scrollIntoView({ block: 'nearest' });\n"
        "      };\n"
        "      const openIndex = () => {\n"
        "        if (!indexModal) return;\n"
        "        indexModal.classList.add('open');\n"
        "        indexModal.setAttribute('aria-hidden', 'false');\n"
        "        refreshIndexLinks();\n"
        "        if (!selectById(indexHash)) {\n"
        "          setSelected(0);\n"
        "        }\n"
        "        if (indexBody) indexBody.focus();\n"
        "      };\n"
        "      const closeIndex = () => {\n"
        "        if (!indexModal) return;\n"
        "        indexModal.classList.remove('open');\n"
        "        indexModal.setAttribute('aria-hidden', 'true');\n"
        "      };\n"
        "      if (navButton) {\n"
        "        navButton.addEventListener('click', openIndex);\n"
        "      }\n"
        "      if (indexBackdrop) {\n"
        "        indexBackdrop.addEventListener('click', closeIndex);\n"
        "      }\n"
        "      document.addEventListener('keydown', (event) => {\n"
        "        const modalOpen = indexModal && indexModal.classList.contains('open');\n"
        "        if (event.key === 'i' && !modalOpen) {\n"
        "          event.preventDefault();\n"
        "          openIndex();\n"
        "          return;\n"
        "        }\n"
        "        if (event.key === 'h' && !modalOpen) {\n"
        "          if (indexHref) {\n"
        "            event.preventDefault();\n"
        "            window.location.href = indexHref;\n"
        "            return;\n"
        "          }\n"
        "        }\n"
        "        if (modalOpen) {\n"
        "          if (event.key === 'Escape') {\n"
        "            event.preventDefault();\n"
        "            closeIndex();\n"
        "            return;\n"
        "          }\n"
        "          if (event.key === 'Enter') {\n"
        "            event.preventDefault();\n"
        "            if (indexSelected >= 0 && indexSelected < indexLinks.length) {\n"
        "              indexLinks[indexSelected].click();\n"
        "            }\n"
        "            return;\n"
        "          }\n"
        "          if (event.key === 'j') {\n"
        "            event.preventDefault();\n"
        "            if (!indexLinks.length) {\n"
        "              if (indexBody) indexBody.scrollBy({ top: 80, left: 0, behavior: 'auto' });\n"
        "              return;\n"
        "            }\n"
        "            setSelected(indexSelected + 1);\n"
        "            return;\n"
        "          }\n"
        "          if (event.key === 'k') {\n"
        "            event.preventDefault();\n"
        "            if (!indexLinks.length) {\n"
        "              if (indexBody) indexBody.scrollBy({ top: -80, left: 0, behavior: 'auto' });\n"
        "              return;\n"
        "            }\n"
        "            setSelected(indexSelected - 1);\n"
        "            return;\n"
        "          }\n"
        "          if (event.key === 'l') {\n"
        "            event.preventDefault();\n"
        "            if (indexSelected >= 0 && indexSelected < indexLinks.length) {\n"
        "              indexLinks[indexSelected].click();\n"
        "            }\n"
        "            return;\n"
        "          }\n"
        "        }\n"
        "      });\n"
        "      let scrollDelta = 0;\n"
        "      let scrollScheduled = false;\n"
        "      const flushScroll = () => {\n"
        "        window.scrollBy({ top: scrollDelta, left: 0, behavior: 'auto' });\n"
        "        scrollDelta = 0;\n"
        "        scrollScheduled = false;\n"
        "      };\n"
        "      document.addEventListener('keydown', (event) => {\n"
        "        const tag = event.target && event.target.tagName;\n"
        "        if (tag === 'INPUT' || tag === 'TEXTAREA' || event.target.isContentEditable) return;\n"
        "        if (event.key === 'j') {\n"
        "          event.preventDefault();\n"
        "          scrollDelta += 80;\n"
        "        } else if (event.key === 'k') {\n"
        "          event.preventDefault();\n"
        "          scrollDelta -= 80;\n"
        "        } else {\n"
        "          return;\n"
        "        }\n"
        "        if (!scrollScheduled) {\n"
        "          scrollScheduled = true;\n"
        "          requestAnimationFrame(flushScroll);\n"
        "        }\n"
        "      });\n"
        "    </script>\n"
        "  </body>\n"
        "</html>\n"
    )


def _render_text_block(
    block: TextBlock,
    toc_text: str,
    heading_ids: dict[int, str],
    numbering: dict[int, str],
    index: int,
) -> str:
    kind_class = f"block-{block.kind}"
    if block.kind == "toc":
        return f'<section class="block {kind_class}">{toc_text}</section>'
    text_source = block.text
    text = _escape_html(text_source)
    if block.kind in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        prefix = numbering.get(index, "")
        if prefix:
            text = _escape_html(_format_heading_label(prefix, text_source))
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
                dark_result.error or light_result.error or "Python render failed"
            )
            return f'<section class="block block-pyimage">Python render error: {error}</section>'
        dark_encoded = (
            base64.b64encode(dark_result.rendered_data.encode("utf-8")).decode("utf-8")
            if dark_result.rendered_data
            else None
        )
        light_encoded = (
            base64.b64encode(light_result.rendered_data.encode("utf-8")).decode("utf-8")
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
    canvas_id = f"gvim-three-{index}"
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


def _rewrite_map_source(source: str, marker_color: str) -> str:
    updated = source
    updated = re.sub(
        r"(color\s*:\s*)(['\"])[^'\"]+\2",
        rf"\1'{marker_color}'",
        updated,
    )
    updated = re.sub(
        r"(fillColor\s*:\s*)(['\"])[^'\"]+\2",
        rf"\1'{marker_color}'",
        updated,
    )
    return updated


def _build_toc(
    document: BlockDocument,
    numbering: dict[int, str],
) -> tuple[str, dict[int, str]]:
    headings: list[tuple[int, str, str]] = []
    heading_ids: dict[int, str] = {}
    seen: dict[str, int] = {}
    for index, block in enumerate(document.blocks):
        if isinstance(block, TextBlock) and block.kind in {
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        }:
            text = block.text.strip().splitlines()[0] if block.text.strip() else ""
            anchor = _slugify_heading(text)
            count = seen.get(anchor, 0) + 1
            seen[anchor] = count
            if count > 1:
                anchor = f"{anchor}-{count}"
            heading_ids[index] = anchor
            prefix = numbering.get(index, "")
            label = _format_heading_label(prefix, text)
            headings.append((index, block.kind, label))

    if not headings:
        return (
            '<div class="toc-index">Index</div>'
            '<div class="toc-empty">(No headings yet)</div>',
            heading_ids,
        )

    lines = ['<div class="toc-index">Index</div>']
    for index, kind, text in headings:
        anchor = heading_ids.get(index)
        if not anchor:
            continue
        anchor_link = f'- <a href="#{anchor}">{_escape_html(text)}</a>'
        if kind == "h1":
            lines.append(f'<div class="toc-line depth-1">{anchor_link}</div>')
        elif kind == "h2":
            lines.append(f'<div class="toc-line depth-2">{anchor_link}</div>')
        elif kind == "h3":
            lines.append(f'<div class="toc-line depth-3">{anchor_link}</div>')
        elif kind == "h4":
            lines.append(f'<div class="toc-line depth-4">{anchor_link}</div>')
        elif kind == "h5":
            lines.append(f'<div class="toc-line depth-5">{anchor_link}</div>')
        else:
            lines.append(f'<div class="toc-line depth-6">{anchor_link}</div>')
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


def _format_heading_label(prefix: str, text: str) -> str:
    prefix = prefix.strip()
    text = text.strip()
    if not prefix:
        return text
    if not text:
        return prefix
    return f"{prefix} {text}"


def _build_index_html(paths: list[tuple[Path, str]], ui_mode: str, title: str) -> str:
    dark = colors_for("dark")
    light = colors_for("light")
    tree_html = _build_index_tree_html(paths, "")
    safe_title = _escape_html(title)
    return (
        "<!doctype html>\n"
        f'<html data-theme="{ui_mode}">\n'
        "  <head>\n"
        '    <meta charset="utf-8" />\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f"    <title>{safe_title}</title>\n"
        "    <style>\n"
        "      :root {\n"
        "        color-scheme: light dark;\n"
        "      }\n"
        '      :root[data-theme="dark"] {\n'
        f"        --body-background: {dark.export_body_background};\n"
        f"        --body-text: {dark.export_body_text};\n"
        f"        --title-color: {dark.export_title};\n"
        f"        --link-color: {dark.export_body};\n"
        f"        --muted-color: {dark.export_toc};\n"
        f"        --toggle-bg: {dark.export_toggle_bg};\n"
        f"        --toggle-text: {dark.export_toggle_text};\n"
        f"        --toggle-border: {dark.export_toggle_border};\n"
        f"        --toggle-active-bg: {dark.export_toggle_active_bg};\n"
        f"        --toggle-active-text: {dark.export_toggle_active_text};\n"
        "      }\n"
        '      :root[data-theme="light"] {\n'
        f"        --body-background: {light.export_body_background};\n"
        f"        --body-text: {light.export_body_text};\n"
        f"        --title-color: {light.export_title};\n"
        f"        --link-color: {light.export_body};\n"
        f"        --muted-color: {light.export_toc};\n"
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
        "        padding: 24px 24px 80px;\n"
        "      }\n"
        f"      h1 {{ font-size: {font.export_title}; color: var(--title-color); margin: 0 0 16px; }}\n"
        f"      .index-tree {{ font-size: {font.export_body}; }}\n"
        "      ul { list-style: none; margin: 0; padding-left: 18px; }\n"
        "      li { margin: 6px 0; }\n"
        "      .dir-name { color: var(--muted-color); font-weight: 600; }\n"
        "      a { color: var(--link-color); text-decoration: none; }\n"
        "      a:hover { text-decoration: underline; }\n"
        "      a:focus { outline: none; }\n"
        "      a.nav-selected { text-decoration: underline; }\n"
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
        "    </style>\n"
        "  </head>\n"
        "  <body>\n"
        '    <div class="theme-toggle" role="group" aria-label="Theme toggle">\n'
        '      <button type="button" data-theme="dark">Dark</button>\n'
        '      <button type="button" data-theme="light">Light</button>\n'
        "    </div>\n"
        "    <main>\n"
        f"      <h1>{safe_title}</h1>\n"
        f"      {tree_html}\n"
        "    </main>\n"
        "    <script>\n"
        f"      const themeDefault = '{ui_mode}';\n"
        "      const themeStorageKey = 'gvim-theme';\n"
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
        "      toggleButtons.forEach((btn) => {\n"
        "        btn.addEventListener('click', () => {\n"
        "          const value = btn.dataset.theme;\n"
        "          applyTheme(value);\n"
        "          setStoredTheme(value);\n"
        "        });\n"
        "      });\n"
        "      const indexLinks = Array.from(document.querySelectorAll('.index-tree a'));\n"
        "      let indexSelected = -1;\n"
        "      const setSelected = (next) => {\n"
        "        if (!indexLinks.length) return;\n"
        "        if (indexSelected >= 0 && indexSelected < indexLinks.length) {\n"
        "          indexLinks[indexSelected].classList.remove('nav-selected');\n"
        "        }\n"
        "        indexSelected = Math.max(0, Math.min(next, indexLinks.length - 1));\n"
        "        const link = indexLinks[indexSelected];\n"
        "        link.classList.add('nav-selected');\n"
        "        link.scrollIntoView({ block: 'nearest' });\n"
        "      };\n"
        "      const selectByHash = () => {\n"
        "        const hash = window.location.hash ? window.location.hash.slice(1) : '';\n"
        "        if (!hash) return false;\n"
        "        const idx = indexLinks.findIndex((link) => link.id === hash);\n"
        "        if (idx < 0) return false;\n"
        "        setSelected(idx);\n"
        "        return true;\n"
        "      };\n"
        "      if (indexLinks.length && !selectByHash()) {\n"
        "        setSelected(0);\n"
        "      }\n"
        "      window.addEventListener('hashchange', () => {\n"
        "        selectByHash();\n"
        "      });\n"
        "      document.addEventListener('keydown', (event) => {\n"
        "        const tag = event.target && event.target.tagName;\n"
        "        if (tag === 'INPUT' || tag === 'TEXTAREA' || event.target.isContentEditable) return;\n"
        "        if (event.key === 'h') {\n"
        "          event.preventDefault();\n"
        "          window.location.href = './index.html';\n"
        "          return;\n"
        "        }\n"
        "        if (event.key === 'j') {\n"
        "          event.preventDefault();\n"
        "          setSelected(indexSelected + 1);\n"
        "          return;\n"
        "        }\n"
        "        if (event.key === 'k') {\n"
        "          event.preventDefault();\n"
        "          setSelected(indexSelected - 1);\n"
        "          return;\n"
        "        }\n"
        "        if (event.key === 'Enter' || event.key === 'l') {\n"
        "          event.preventDefault();\n"
        "          if (indexSelected >= 0 && indexSelected < indexLinks.length) {\n"
        "            indexLinks[indexSelected].click();\n"
        "          }\n"
        "        }\n"
        "      });\n"
        "    </script>\n"
        "  </body>\n"
        "</html>\n"
    )


def _build_index_tree(paths: list[tuple[Path, str]]) -> dict[str, Any]:
    root: dict[str, Any] = {"__files__": []}
    for rel_path, title in paths:
        parts = rel_path.parts
        if not parts:
            continue
        node: dict[str, Any] = root
        for part in parts[:-1]:
            child = node.get(part)
            if not isinstance(child, dict):
                child = {"__files__": []}
                node[part] = child
            node = cast(dict[str, Any], child)
        files = cast(list[tuple[str, Path, str]], node.setdefault("__files__", []))
        files.append((parts[-1], rel_path, title))
    return root


def _render_index_tree(
    node: dict[str, Any],
    base_prefix: str,
    is_root: bool = False,
) -> str:
    files = cast(list[tuple[str, Path, str]], node.get("__files__", []))
    files.sort(key=lambda item: item[0].lower())
    dirs = [key for key in node.keys() if key != "__files__"]
    dirs.sort(key=str.lower)
    lines = [
        '<ul class="index-tree">' if is_root else "<ul>",
    ]
    for dirname in dirs:
        lines.append('<li class="dir">')
        lines.append(f'<div class="dir-name">{_escape_html(dirname)}/</div>')
        child = node.get(dirname)
        if isinstance(child, dict):
            lines.append(_render_index_tree(child, base_prefix))
        lines.append("</li>")
    for filename, rel_path, title in files:
        url = _encode_rel_path(rel_path, base_prefix)
        link_id = _index_link_id(rel_path)
        lines.append(
            f'<li class="file"><a id="{link_id}" href="{url}">{_escape_html(title)}</a></li>'
        )
    lines.append("</ul>")
    return "\n".join(lines)


def _encode_rel_path(path: Path, base_prefix: str) -> str:
    encoded = "/".join(quote(part) for part in path.parts)
    prefix = base_prefix or "./"
    return f"{prefix}{encoded}"


def _build_index_tree_html(paths: list[tuple[Path, str]], base_prefix: str) -> str:
    tree = _build_index_tree(paths)
    return _render_index_tree(tree, base_prefix, is_root=True)


def _index_link_id(rel_path: Path) -> str:
    slug = []
    prev_dash = False
    raw = "/".join(rel_path.parts)
    for ch in raw.lower():
        if ch.isalnum():
            slug.append(ch)
            prev_dash = False
            continue
        if not prev_dash:
            slug.append("-")
            prev_dash = True
    text = "".join(slug).strip("-")
    return f"idx-{text or 'doc'}"
