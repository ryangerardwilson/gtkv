"""Block capability registry."""

from __future__ import annotations

from dataclasses import dataclass

from block_model import LatexBlock, PythonImageBlock, TextBlock, ThreeBlock


@dataclass(frozen=True)
class BlockCapabilities:
    editable: bool
    editor_suffix: str | None
    kind: str | None


_BLOCK_CAPABILITIES: dict[type, BlockCapabilities] = {
    TextBlock: BlockCapabilities(editable=True, editor_suffix=".txt", kind="text"),
    ThreeBlock: BlockCapabilities(editable=True, editor_suffix=".html", kind="three"),
    PythonImageBlock: BlockCapabilities(
        editable=True, editor_suffix=".py", kind="pyimage"
    ),
    LatexBlock: BlockCapabilities(editable=True, editor_suffix=".tex", kind="latex"),
}


def get_block_capabilities(block: object) -> BlockCapabilities | None:
    for block_type, capabilities in _BLOCK_CAPABILITIES.items():
        if isinstance(block, block_type):
            return capabilities
    return None
