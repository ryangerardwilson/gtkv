from __future__ import annotations

import json

import config
from design_constants import colors_for


def default_three_template(
    ui_mode: str | None = None, include_guidance: bool = True
) -> str:
    palette = colors_for(ui_mode or config.get_ui_mode() or "dark")
    material_color = f"0x{palette.three_material:06x}"
    light_color = f"0x{palette.three_light:06x}"
    guidance = (
        "/*\n"
        "Theme note: colors are set globally by your UI mode (dark/light).\n"
        "Override locally by setting explicit colors in this block.\n"
        "Defaults applied: material color, light color, and transparent clear color.\n"
        "\n"
        "Example: Non-interfering snippet that looks great in the UI.\n"
        "You can use scene, camera, renderer, canvas, and THREE.\n"
        "```\n"
        "const geometry = new THREE.BoxGeometry(1, 1, 1);\n"
        f"const material = new THREE.MeshStandardMaterial({{ color: {material_color}, metalness: 0.3, roughness: 0.4 }});\n"
        "const cube = new THREE.Mesh(geometry, material);\n"
        "scene.add(cube);\n"
        f"const light = new THREE.DirectionalLight({light_color}, 1);\n"
        "light.position.set(2, 3, 4);\n"
        "scene.add(light);\n"
        "camera.position.z = 3;\n"
        "function animate() {\n"
        "  requestAnimationFrame(animate);\n"
        "  cube.rotation.x += 0.01;\n"
        "  cube.rotation.y += 0.015;\n"
        "  renderer.render(scene, camera);\n"
        "}\n"
        "animate();\n"
        "```\n"
        "*/\n\n"
    )
    body = (
        "// GTKV Three.js block (module JS)\n"
        "// You can use scene, camera, renderer, canvas, and THREE.\n"
        "const geometry = new THREE.BoxGeometry(1, 1, 1);\n"
        f"const material = new THREE.MeshStandardMaterial({{ color: {material_color}, metalness: 0.3, roughness: 0.4 }});\n"
        "const cube = new THREE.Mesh(geometry, material);\n"
        "scene.add(cube);\n"
        f"const light = new THREE.DirectionalLight({light_color}, 1);\n"
        "light.position.set(2, 3, 4);\n"
        "scene.add(light);\n"
        "camera.position.z = 3;\n"
        "function animate() {\n"
        "  requestAnimationFrame(animate);\n"
        "  cube.rotation.x += 0.01;\n"
        "  cube.rotation.y += 0.015;\n"
        "  renderer.render(scene, camera);\n"
        "}\n"
        "animate();\n"
    )
    if include_guidance:
        return guidance
    return body


def render_three_html(source: str, ui_mode: str | None = None) -> str:
    palette = colors_for(ui_mode or config.get_ui_mode() or "dark")
    text_color = palette.webkit_three_text
    clear_color = f"0x{palette.three_clear:06x}"
    src = "__GTKV_THREE_SRC__"
    js_source = json.dumps(source)
    return (
        "<!doctype html>\n"
        "<html>\n"
        "  <head>\n"
        '    <meta charset="utf-8" />\n'
        f"    <style>html, body {{ margin: 0; background: transparent; color: {text_color}; }} canvas {{ display: block; }}</style>\n"
        "  </head>\n"
        "  <body>\n"
        '    <canvas id="gtkv-canvas"></canvas>\n'
        '    <script type="module">\n'
        "      const error = (msg) => {\n"
        "        const el = document.createElement('pre');\n"
        "        el.textContent = msg;\n"
        "        el.style.whiteSpace = 'pre-wrap';\n"
        "        el.style.padding = '12px';\n"
        "        document.body.appendChild(el);\n"
        "      };\n"
        f'      const src = "{src}";\n'
        f"      const userSource = {js_source};\n"
        "      const moduleUrl = URL.createObjectURL(new Blob([userSource], { type: 'text/javascript' }));\n"
        "      import(src).then((THREE) => {\n"
        "        const canvas = document.getElementById('gtkv-canvas');\n"
        "        const scene = new THREE.Scene();\n"
        "        const camera = new THREE.PerspectiveCamera(60, innerWidth/innerHeight, 0.1, 1000);\n"
        "        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, canvas });\n"
        f"        renderer.setClearColor({clear_color}, 0);\n"
        "        renderer.setPixelRatio(devicePixelRatio || 1);\n"
        "        const resize = () => {\n"
        "          renderer.setSize(innerWidth, innerHeight);\n"
        "          camera.aspect = innerWidth / innerHeight;\n"
        "          camera.updateProjectionMatrix();\n"
        "        };\n"
        "        resize();\n"
        "        window.addEventListener('resize', resize);\n"
        "        Object.assign(window, { THREE, scene, camera, renderer, canvas });\n"
        "        import(moduleUrl).then(() => {\n"
        "          URL.revokeObjectURL(moduleUrl);\n"
        "        }).catch((err) => {\n"
        "          error(String(err));\n"
        "        });\n"
        "      }).catch((err) => {\n"
        "        error(String(err));\n"
        "      });\n"
        "    </script>\n"
        "  </body>\n"
        "</html>\n"
    )
