"""Document actions and state mutations."""

from __future__ import annotations

from pathlib import Path

from app_state import AppState
from block_model import LatexBlock, PythonImageBlock, TextBlock, ThreeBlock
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
    state.document.insert_block_after(insert_at, ThreeBlock(default_three_template()))
    state.view.set_document(state.document)
    state.view.move_selection(1)
    return True


def insert_python_image_block(state: AppState) -> bool:
    if state.document is None or state.view is None:
        return False
    insert_at = state.view.get_selected_index()
    template = (
        "import matplotlib.pyplot as plt\n\n"
        "fig, ax = plt.subplots()\n"
        "ax.plot([0, 1, 2], [0, 1, 0.5])\n"
        "fig.savefig(__gtkv__.renderer, format=\"svg\", dpi=200, transparent=True, bbox_inches=\"tight\")\n"
    )
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


def move_selection(state: AppState, delta: int) -> bool:
    if state.view is None:
        return False
    state.view.move_selection(delta)
    return True


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
        content = block.text
    elif isinstance(block, ThreeBlock):
        content = block.source
    elif isinstance(block, PythonImageBlock):
        content = block.source
    elif isinstance(block, LatexBlock):
        content = block.source
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
    else:
        state.document.set_text_block(index, updated_text)
    state.view.set_document(state.document)
    return True
