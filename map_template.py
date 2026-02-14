from __future__ import annotations

import json

import config
from design_constants import colors_for


LEAFLET_CSS_CDN = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
LEAFLET_JS_CDN = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"


def render_map_html(source: str, ui_mode: str | None = None) -> str:
    palette = colors_for(ui_mode or config.get_ui_mode() or "dark")
    js_source = json.dumps(source)
    return (
        "<!doctype html>\n"
        "<html>\n"
        "  <head>\n"
        '    <meta charset="utf-8" />\n'
        f'    <link rel="stylesheet" href="{LEAFLET_CSS_CDN}" />\n'
        "    <style>\n"
        "      html, body { margin: 0; background: transparent; width: 100%; height: 100%; }\n"
        "      #map { width: 100%; height: 100%; }\n"
        "      .leaflet-container { background: transparent; }\n"
        "    </style>\n"
        "  </head>\n"
        "  <body>\n"
        '    <div id="map"></div>\n'
        f'    <script src="{LEAFLET_JS_CDN}"></script>\n'
        "    <script>\n"
        f"      const userSource = {js_source};\n"
        "      const map = L.map('map', { zoomControl: false, attributionControl: true });\n"
        f"      const tileLayer = L.tileLayer('{palette.map_tile_url}', {{ attribution: '{palette.map_tile_attr}' }}).addTo(map);\n"
        "      Object.assign(window, { L, map, tileLayer });\n"
        "      try {\n"
        "        const fn = new Function('L', 'map', 'tileLayer', userSource);\n"
        "        fn(L, map, tileLayer);\n"
        "      } catch (err) {\n"
        "        const el = document.createElement('pre');\n"
        "        el.textContent = String(err);\n"
        "        el.style.whiteSpace = 'pre-wrap';\n"
        "        el.style.padding = '12px';\n"
        "        el.style.margin = '12px';\n"
        "        el.style.borderRadius = '8px';\n"
        f"        el.style.background = '{palette.webkit_map_error_background}';\n"
        f"        el.style.color = '{palette.webkit_map_error_text}';\n"
        "        document.body.appendChild(el);\n"
        "      }\n"
        "    </script>\n"
        "  </body>\n"
        "</html>\n"
    )
