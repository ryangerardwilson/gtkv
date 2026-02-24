"""Document actions and state mutations."""

from __future__ import annotations

import copy
from typing import Sequence
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
    if kind in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        prior_blocks = [
            block
            for block in state.document.blocks[: insert_at + 1]
            if isinstance(block, TextBlock)
        ]
        kind = _resolve_heading_kind(prior_blocks, kind)
    if kind == "title":
        placeholder = "Title"
    elif kind == "h1":
        placeholder = "Heading1"
    elif kind == "h2":
        placeholder = "Heading2"
    elif kind == "h3":
        placeholder = "Heading3"
    elif kind == "h4":
        placeholder = "Heading4"
    elif kind == "h5":
        placeholder = "Heading5"
    elif kind == "h6":
        placeholder = "Heading6"
    state.document.insert_block_after(insert_at, TextBlock(placeholder, kind=kind))
    inserted_index = min(insert_at + 1, len(state.document.blocks) - 1)
    inserted_block = state.document.blocks[inserted_index]
    scroll_position = state.view.get_scroll_position()
    state.view.insert_widget_after(insert_at, inserted_block, state.document)
    state.view.set_selected_index(inserted_index)
    state.view.set_scroll_position(scroll_position)
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
    inserted_index = min(insert_at + 1, len(state.document.blocks) - 1)
    inserted_block = state.document.blocks[inserted_index]
    scroll_position = state.view.get_scroll_position()
    state.view.insert_widget_after(insert_at, inserted_block, state.document)
    state.view.set_selected_index(inserted_index)
    state.view.set_scroll_position(scroll_position)
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
    inserted_index = min(insert_at + 1, len(state.document.blocks) - 1)
    inserted_block = state.document.blocks[inserted_index]
    scroll_position = state.view.get_scroll_position()
    state.view.insert_widget_after(insert_at, inserted_block, state.document)
    state.view.set_selected_index(inserted_index)
    state.view.set_scroll_position(scroll_position)
    return True


def insert_python_image_block(state: AppState) -> bool:
    if state.document is None or state.view is None:
        return False
    insert_at = state.view.get_selected_index()
    template = _PY_GUIDANCE
    state.document.insert_block_after(
        insert_at, PythonImageBlock(template, format="svg")
    )
    inserted_index = min(insert_at + 1, len(state.document.blocks) - 1)
    inserted_block = state.document.blocks[inserted_index]
    scroll_position = state.view.get_scroll_position()
    state.view.insert_widget_after(insert_at, inserted_block, state.document)
    state.view.set_selected_index(inserted_index)
    state.view.set_scroll_position(scroll_position)
    return True


def insert_latex_block(state: AppState) -> bool:
    if state.document is None or state.view is None:
        return False
    insert_at = state.view.get_selected_index()
    template = r"\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}"
    state.document.insert_block_after(insert_at, LatexBlock(template))
    inserted_index = min(insert_at + 1, len(state.document.blocks) - 1)
    inserted_block = state.document.blocks[inserted_index]
    scroll_position = state.view.get_scroll_position()
    state.view.insert_widget_after(insert_at, inserted_block, state.document)
    state.view.set_selected_index(inserted_index)
    state.view.set_scroll_position(scroll_position)
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
    inserted_index = min(insert_at + 1, len(state.document.blocks) - 1)
    inserted_block = state.document.blocks[inserted_index]
    scroll_position = state.view.get_scroll_position()
    state.view.insert_widget_after(insert_at, inserted_block, state.document)
    state.view.set_selected_index(inserted_index)
    state.view.set_scroll_position(scroll_position)
    return True


def move_selection(state: AppState, delta: int) -> bool:
    if state.view is None:
        return False
    if state.view.visual_active():
        state.view.visual_move(delta)
        return True
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
    if _would_orphan_headings(state.document.blocks, index):
        return None
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


def delete_selected_range(state: AppState) -> list[Block] | None:
    if state.document is None or state.view is None:
        return None
    if not state.document.blocks:
        return None
    if not state.view.visual_active():
        return None
    start, end = state.view.get_visual_range()
    if _would_orphan_heading_range(state.document.blocks, start, end):
        return None
    deleted: list[Block] = []
    for index in range(end, start - 1, -1):
        block = state.document.remove_block(index)
        if block is not None:
            deleted.append(block)
            state.view.remove_widget_at(index, state.document)
    deleted.reverse()
    if state.document.blocks:
        state.view.set_selected_index(
            min(start, len(state.document.blocks) - 1), scroll=True
        )
    else:
        state.view.clear_selection()
    state.view.exit_visual_mode()
    return deleted


def paste_after_selected(state: AppState, block: Block) -> bool:
    if state.document is None or state.view is None:
        return False
    insert_at = state.view.get_selected_index()
    state.document.insert_block_after(insert_at, copy.deepcopy(block))
    inserted_index = min(insert_at + 1, len(state.document.blocks) - 1)
    inserted_block = state.document.blocks[inserted_index]
    state.view.insert_widget_after(insert_at, inserted_block, state.document)
    state.view.set_selected_index(inserted_index)
    state.view.reload_media_at(inserted_index)
    return True


def paste_after_selected_range(state: AppState, blocks: list[Block]) -> bool:
    if state.document is None or state.view is None:
        return False
    if not blocks:
        return False
    insert_at = state.view.get_selected_index()
    current_index = insert_at
    for block in blocks:
        state.document.insert_block_after(current_index, copy.deepcopy(block))
        inserted_index = min(current_index + 1, len(state.document.blocks) - 1)
        inserted_block = state.document.blocks[inserted_index]
        state.view.insert_widget_after(current_index, inserted_block, state.document)
        state.view.reload_media_at(inserted_index)
        current_index = inserted_index
    state.view.set_selected_index(current_index)
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


def yank_selected_range(state: AppState) -> list[Block] | None:
    if state.document is None or state.view is None:
        return None
    if not state.document.blocks:
        return None
    if not state.view.visual_active():
        return None
    start, end = state.view.get_visual_range()
    blocks: list[Block] = []
    for index in range(start, end + 1):
        try:
            blocks.append(copy.deepcopy(state.document.blocks[index]))
        except IndexError:
            return None
    state.view.exit_visual_mode()
    return blocks


def shift_heading_level(state: AppState, delta: int) -> bool:
    if state.document is None or state.view is None:
        return False
    index = state.view.get_selected_index()
    try:
        block = state.document.blocks[index]
    except IndexError:
        return False
    if not isinstance(block, TextBlock):
        return False
    headings = ["h1", "h2", "h3", "h4", "h5", "h6"]
    if block.kind not in headings:
        return False
    current = headings.index(block.kind)
    target = max(0, min(current + delta, len(headings) - 1))
    target_kind = headings[target]
    if target_kind == block.kind:
        return False
    if target > 0 and not _has_parent_before(state.document.blocks, index, target_kind):
        return False
    original_text = block.text
    state.document.remove_block(index)
    state.view.remove_widget_at(index, state.document)
    insert_after = index - 1
    state.document.insert_block_after(insert_after, TextBlock(original_text, kind=target_kind))
    inserted_index = min(index, len(state.document.blocks) - 1)
    inserted_block = state.document.blocks[inserted_index]
    state.view.insert_widget_after(insert_after, inserted_block, state.document)
    state.view.replace_widget_at(inserted_index, state.document)
    state.view.refresh_heading_numbering(state.document)
    state.view.set_selected_index(inserted_index)
    return True


def _has_parent_before(blocks: Sequence[Block], index: int, kind: str) -> bool:
    headings = ["h1", "h2", "h3", "h4", "h5", "h6"]
    if kind not in headings:
        return True
    level = headings.index(kind)
    if level == 0:
        return True
    required_level = level - 1
    for block in reversed(blocks[:index]):
        if not isinstance(block, TextBlock):
            continue
        if block.kind not in headings:
            continue
        seen_level = headings.index(block.kind)
        if seen_level < required_level:
            return False
        if seen_level == required_level:
            return True
        continue
    return False


def _would_orphan_headings(blocks: Sequence[Block], remove_index: int) -> bool:
    remaining = [block for i, block in enumerate(blocks) if i != remove_index]
    return _has_orphaned_heading(remaining)


def _would_orphan_heading_range(blocks: Sequence[Block], start: int, end: int) -> bool:
    remaining = [block for i, block in enumerate(blocks) if not (start <= i <= end)]
    return _has_orphaned_heading(remaining)


def _has_orphaned_heading(blocks: Sequence[Block]) -> bool:
    headings = ["h1", "h2", "h3", "h4", "h5", "h6"]
    stack: list[str] = []
    for block in blocks:
        if not isinstance(block, TextBlock):
            continue
        if block.kind not in headings:
            continue
        level = headings.index(block.kind) + 1
        if level > 1 and len(stack) < level - 1:
            return True
        stack = stack[: level - 1]
        if len(stack) < level:
            stack.append(block.kind)
        else:
            stack[level - 1] = block.kind
    return False


def blocks_to_text(blocks: Sequence[Block]) -> str:
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, TextBlock):
            parts.append(block.text)
        elif isinstance(block, ThreeBlock):
            parts.append(block.source)
        elif isinstance(block, PythonImageBlock):
            parts.append(block.source)
        elif isinstance(block, LatexBlock):
            parts.append(block.source)
        elif isinstance(block, MapBlock):
            parts.append(block.source)
    normalized = [part.rstrip("\n") for part in parts]
    return "\n\n".join(normalized)


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

_PY_GUIDANCE_MARKER = "# PYIMAGE_BLOCK"

_PY_GUIDANCE = (
    f"{_PY_GUIDANCE_MARKER}\n"
    "import numpy as np\n"
    "plot_func(\n"
    "    x=np.linspace(-5, 5, 100),\n"
    "    y1=lambda x: 0.5 * x + 1,\n"
    "    y2=lambda x: 0.3 * x + 2,\n"
    '    title="My Plot"\n'
    ")\n"
    "\n"
    '"""\n'
    "HELPER DOCS \n"
    "-----------\n"
    "\n"
    'plot_coord((2, 3), (4, 5), title="My Plot")\n'
    "# Types: \n"
    "- plot_coord: coords = tuple[float, float]\n"
    "- title = str | None\n"
    "\n"
    "plot_func(\n"
    "    x=np.linspace(-5, 5, 100),\n"
    "    y1=lambda x: 0.5 * x + 1,\n"
    "    y2=lambda x: 0.3 * x + 2,\n"
    "    y3_custom_name=lambda x: 0.4 * x + 4,\n"
    '    title="My Plot"\n'
    ")\n"
    "# Types: \n"
    "- plot_func: x = sequence[float] \n"
    "- y* = sequence[float] or callable(x) -> sequence[float]\n"
    "- title = str | None\n"
    '"""\n\n'
)

_PY_SAMPLE = (
    "import numpy as np\n"
    "plot_func(\n"
    "    x=np.linspace(-5, 5, 100),\n"
    "    y1=lambda x: 0.5 * x + 1,\n"
    "    y2=lambda x: 0.3 * x + 2,\n"
    '    title="My Plot"\n'
    ")\n"
)


def _prepend_guidance(kind: str, content: str) -> str:
    if kind == "pyimage":
        guidance = _PY_GUIDANCE
    elif kind == "map":
        guidance = _MAP_GUIDANCE
    else:
        guidance = _THREE_GUIDANCE
    stripped = content.lstrip()
    if kind == "pyimage" and _PY_GUIDANCE_MARKER in content:
        return content
    if kind == "pyimage" and "LAST RUNTIME ERROR:" in content:
        return content
    if stripped.startswith(guidance.strip()):
        return content
    if kind == "pyimage" and guidance.strip() in content:
        return content
    if kind == "pyimage" and stripped.startswith(_PY_SAMPLE.strip()):
        return guidance
    return f"{guidance}{content}"
def _resolve_heading_kind(blocks: Sequence[TextBlock], kind: str) -> str:
    order = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
    target = order.get(kind)
    if target is None or target == 1:
        return kind
    highest = 0
    for block in blocks:
        if isinstance(block, TextBlock) and block.kind in order:
            highest = max(highest, order[block.kind])
    if highest >= target - 1:
        return kind
    return {value: key for key, value in order.items()}.get(highest + 1, "h1")
