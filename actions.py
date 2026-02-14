"""Document actions and state mutations."""

from __future__ import annotations

import copy
from pathlib import Path

import config
from design_constants import colors_for
from app_state import AppState
from block_model import (
    Block,
    LatexBlock,
    MapBlock,
    PythonImageBlock,
    TextBlock,
    ThreeBlock,
)
from block_registry import get_block_capabilities
from three_template import default_three_template


def insert_text_block(state: AppState, kind: str = "body") -> bool:
    if state.document is None or state.view is None:
        return False
    insert_at = state.view.get_selected_index()
    placeholder = "New text block"
    if kind == "title":
        placeholder = "Title"
    elif kind == "h1":
        placeholder = "Heading1"
    elif kind == "h2":
        placeholder = "Heading2"
    elif kind == "h3":
        placeholder = "Heading3"
    state.document.insert_block_after(insert_at, TextBlock(placeholder, kind=kind))
    state.view.set_document(state.document)
    return True


def insert_toc_block(state: AppState) -> bool:
    if state.document is None or state.view is None:
        return False
    for index, block in enumerate(state.document.blocks):
        if isinstance(block, TextBlock) and block.kind == "toc":
            state.view.set_selected_index(index)
            state.view.center_on_index(index)
            return True
    insert_at = state.view.get_selected_index()
    state.document.insert_block_after(insert_at, TextBlock("", kind="toc"))
    state.view.set_document(state.document)
    return True


def insert_image_block(state: AppState, path: Path) -> bool:
    return False


def insert_three_block(state: AppState) -> bool:
    if state.document is None or state.view is None:
        return False
    insert_at = state.view.get_selected_index()
    state.document.insert_block_after(
        insert_at,
        ThreeBlock(
            default_three_template(
                ui_mode=config.get_ui_mode() or "dark", include_guidance=True
            )
        ),
    )
    state.view.set_document(state.document)
    state.view.move_selection(1)
    return True


def insert_python_image_block(state: AppState) -> bool:
    if state.document is None or state.view is None:
        return False
    insert_at = state.view.get_selected_index()
    template = _PY_GUIDANCE
    state.document.insert_block_after(
        insert_at, PythonImageBlock(template, format="svg")
    )
    state.view.set_document(state.document)
    state.view.move_selection(1)
    return True


def insert_latex_block(state: AppState) -> bool:
    if state.document is None or state.view is None:
        return False
    insert_at = state.view.get_selected_index()
    template = r"\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}"
    state.document.insert_block_after(insert_at, LatexBlock(template))
    state.view.set_document(state.document)
    state.view.move_selection(1)
    return True


def insert_map_block(state: AppState) -> bool:
    if state.document is None or state.view is None:
        return False
    insert_at = state.view.get_selected_index()
    palette = colors_for(config.get_ui_mode() or "dark")
    template = (
        "// Leaflet globals: L, map, tileLayer\n"
        "const points = [\n"
        "  [40.7484, -73.9857],\n"
        "  [51.5072, -0.1276],\n"
        "  [48.8566, 2.3522],\n"
        "];\n"
        "points.forEach(([lat, lon]) => {\n"
        "  L.circleMarker([lat, lon], {\n"
        "    radius: 5,\n"
        f"    color: '{palette.map_marker}',\n"
        f"    fillColor: '{palette.map_marker}',\n"
        "    fillOpacity: 0.9,\n"
        "  }).addTo(map);\n"
        "});\n"
        "const bounds = L.latLngBounds(points);\n"
        "map.fitBounds(bounds.pad(0.2));\n"
    )
    template = _prepend_guidance("map", template)
    state.document.insert_block_after(insert_at, MapBlock(template))
    state.view.set_document(state.document)
    state.view.move_selection(1)
    return True


def move_selection(state: AppState, delta: int) -> bool:
    if state.view is None:
        return False
    state.view.move_selection(delta)
    return True


def move_block(state: AppState, delta: int) -> bool:
    if state.document is None or state.view is None:
        return False
    index = state.view.get_selected_index()
    target = index + delta
    if not state.document.move_block(index, target):
        return False
    state.view.move_widget(index, target)
    state.view.set_selected_index(target)
    return True


def delete_selected_block(state: AppState) -> Block | None:
    if state.document is None or state.view is None:
        return None
    if not state.document.blocks:
        return None
    index = state.view.get_selected_index()
    block = state.document.remove_block(index)
    if block is None:
        return None
    state.view.remove_widget_at(index, state.document)
    if state.document.blocks:
        state.view.set_selected_index(
            min(index, len(state.document.blocks) - 1), scroll=True
        )
    else:
        state.view.clear_selection()
    return block


def paste_after_selected(state: AppState, block: Block) -> bool:
    if state.document is None or state.view is None:
        return False
    insert_at = state.view.get_selected_index()
    state.document.insert_block_after(insert_at, copy.deepcopy(block))
    inserted_index = min(insert_at + 1, len(state.document.blocks) - 1)
    inserted_block = state.document.blocks[inserted_index]
    state.view.insert_widget_after(insert_at, inserted_block, state.document)
    state.view.set_selected_index(inserted_index)
    return True


def yank_selected_block(state: AppState) -> Block | None:
    if state.document is None or state.view is None:
        return None
    if not state.document.blocks:
        return None
    index = state.view.get_selected_index()
    try:
        block = state.document.blocks[index]
    except IndexError:
        return None
    return copy.deepcopy(block)


def select_first(state: AppState) -> bool:
    if state.view is None:
        return False
    state.view.select_first()
    return True


def select_last(state: AppState) -> bool:
    if state.view is None:
        return False
    state.view.select_last()
    return True


def get_selected_edit_payload(
    state: AppState,
) -> tuple[int, str, str, str] | None:
    if state.document is None or state.view is None:
        return None
    index = state.view.get_selected_index()
    block = state.document.blocks[index]
    capabilities = get_block_capabilities(block)
    if not capabilities or not capabilities.editable:
        return None
    if not capabilities.editor_suffix or not capabilities.kind:
        return None

    if isinstance(block, TextBlock):
        if block.kind == "toc":
            return None
        content = block.text
    elif isinstance(block, ThreeBlock):
        content = _prepend_guidance("three", block.source)
    elif isinstance(block, PythonImageBlock):
        content = _prepend_guidance("pyimage", block.source)
    elif isinstance(block, LatexBlock):
        content = block.source
    elif isinstance(block, MapBlock):
        content = _prepend_guidance("map", block.source)
    else:
        return None

    return index, content, capabilities.editor_suffix, capabilities.kind


def update_block_from_editor(
    state: AppState, index: int, kind: str, updated_text: str
) -> bool:
    if state.document is None or state.view is None:
        return False
    if kind == "three":
        state.document.set_three_block(index, updated_text)
    elif kind == "pyimage":
        state.document.set_python_image_block(index, updated_text)
    elif kind == "latex":
        state.document.set_latex_block(index, updated_text)
    elif kind == "map":
        state.document.set_map_block(index, updated_text)
    else:
        state.document.set_text_block(index, updated_text)
    return True




_THREE_GUIDANCE = (
    "/*\n"
    "Theme note: colors are set globally by your UI mode (dark/light).\n"
    "Override locally by setting explicit colors in this block.\n"
    "Defaults applied: material color, light color, and transparent clear color.\n"
    "\n"
    "Example: Non-interfering snippet that looks great in the UI.\n"
    "You can use scene, camera, renderer, canvas, and THREE.\n"
    "```\n"
    "const geometry = new THREE.BoxGeometry(1, 1, 1);\n"
    "const material = new THREE.MeshStandardMaterial({ color: 0xaaaaaa, metalness: 0.3, roughness: 0.4 });\n"
    "const cube = new THREE.Mesh(geometry, material);\n"
    "scene.add(cube);\n"
    "const light = new THREE.DirectionalLight(0xffffff, 1);\n"
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

_MAP_GUIDANCE = (
    "/*\n"
    "Theme note: colors are set globally by your UI mode (dark/light).\n"
    "Override locally by setting explicit colors in this block.\n"
    "Defaults applied: basemap tiles and marker stroke/fill colors.\n"
    "*/\n\n"
)

_PY_GUIDANCE = (
    "\"\"\"\n"
    "Theme note: colors are set globally by your UI mode (dark/light).\n"
    "Override locally by setting explicit colors in this block.\n"
    "Defaults applied: matplotlib text/ticks/axes colors and transparent figure.\n"
    "\n"
    "Example: Non-interfering snippet that looks great in the UI\n"
    "```\n"
    "import matplotlib.pyplot as plt\n"
    "\n"
    "fig, ax = plt.subplots()\n"
    "ax.plot([0, 1, 2], [0, 1, 0.5])\n"
    "ax.set_title(\"Sample plot\")\n"
    "fig.savefig(__gtkv__.renderer, format=\"svg\", dpi=200, transparent=True, bbox_inches=\"tight\")\n"
    "```\n"
    "\"\"\"\n\n"
)


def _prepend_guidance(kind: str, content: str) -> str:
    if kind == "pyimage":
        guidance = _PY_GUIDANCE
    elif kind == "map":
        guidance = _MAP_GUIDANCE
    else:
        guidance = _THREE_GUIDANCE
    if content.lstrip().startswith(guidance.strip()):
        return content
    return f"{guidance}{content}"
