from __future__ import annotations

import json
from pathlib import Path


def render_latex_html(source: str) -> str:
    latex = json.dumps(source)
    css_uri = Path(__file__).with_name("katex.min.css").resolve().as_uri()
    js_uri = Path(__file__).with_name("katex.min.js").resolve().as_uri()
    return (
        "<!doctype html>\n"
        "<html>\n"
        "  <head>\n"
        "    <meta charset=\"utf-8\" />\n"
        f"    <link rel=\"stylesheet\" href=\"{css_uri}\" />\n"
        "    <style>html, body { margin: 0; background: transparent; color: #d0d0d0; }</style>\n"
        "  </head>\n"
        "  <body>\n"
        "    <div id=\"gtkv-latex\" style=\"padding: 12px;\"></div>\n"
        f"    <script src=\"{js_uri}\"></script>\n"
        "    <script>\n"
        f"      const latex = {latex};\n"
        "      const target = document.getElementById('gtkv-latex');\n"
        "      try {\n"
        "        katex.render(latex, target, { throwOnError: false, displayMode: true });\n"
        "      } catch (err) {\n"
        "        target.textContent = String(err);\n"
        "      }\n"
        "    </script>\n"
        "  </body>\n"
        "</html>\n"
    )
