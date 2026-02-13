from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

from three_template import default_three_template


@dataclass(frozen=True)
class TextBlock:
    text: str


@dataclass(frozen=True)
class ThreeBlock:
    source: str
    title: str = ""


@dataclass(frozen=True)
class PythonImageBlock:
    source: str
    format: str = "svg"
    rendered_data: str | None = None
    rendered_hash: str | None = None
    last_error: str | None = None
    rendered_path: str | None = None


@dataclass(frozen=True)
class LatexBlock:
    source: str


Block = TextBlock | ThreeBlock | PythonImageBlock | LatexBlock


class BlockDocument:
    def __init__(self, blocks: Sequence[Block], path: Path | None = None) -> None:
        self._blocks: List[Block] = list(blocks)
        self._path = path
        self._dirty = False

    @property
    def blocks(self) -> List[Block]:
        return self._blocks

    @property
    def path(self) -> Path | None:
        return self._path

    def set_path(self, path: Path | None) -> None:
        self._path = path

    @property
    def dirty(self) -> bool:
        return self._dirty

    def clear_dirty(self) -> None:
        self._dirty = False

    def append_block(self, block: Block) -> None:
        self._blocks.append(block)
        self._dirty = True

    def insert_block_after(self, index: int, block: Block) -> None:
        if index < 0:
            self._blocks.insert(0, block)
        elif index >= len(self._blocks) - 1:
            self._blocks.append(block)
        else:
            self._blocks.insert(index + 1, block)
        self._dirty = True

    def set_text_block(self, index: int, text: str) -> None:
        if index < 0 or index >= len(self._blocks):
            return
        block = self._blocks[index]
        if isinstance(block, TextBlock):
            self._blocks[index] = TextBlock(text)
            self._dirty = True

    def set_three_block(self, index: int, source: str) -> None:
        if index < 0 or index >= len(self._blocks):
            return
        block = self._blocks[index]
        if isinstance(block, ThreeBlock):
            self._blocks[index] = ThreeBlock(source, title=block.title)
            self._dirty = True

    def set_python_image_block(self, index: int, source: str) -> None:
        if index < 0 or index >= len(self._blocks):
            return
        block = self._blocks[index]
        if isinstance(block, PythonImageBlock):
            self._blocks[index] = PythonImageBlock(
                source,
                format=block.format,
                rendered_data=None,
                rendered_hash=None,
                last_error=None,
                rendered_path=None,
            )
            self._dirty = True

    def set_python_image_render(
        self,
        index: int,
        rendered_data: str | None,
        rendered_hash: str | None,
        last_error: str | None,
        rendered_path: str | None,
    ) -> None:
        if index < 0 or index >= len(self._blocks):
            return
        block = self._blocks[index]
        if isinstance(block, PythonImageBlock):
            self._blocks[index] = PythonImageBlock(
                block.source,
                format=block.format,
                rendered_data=rendered_data,
                rendered_hash=rendered_hash,
                last_error=last_error,
                rendered_path=rendered_path,
            )
            self._dirty = True

    def set_latex_block(self, index: int, source: str) -> None:
        if index < 0 or index >= len(self._blocks):
            return
        block = self._blocks[index]
        if isinstance(block, LatexBlock):
            self._blocks[index] = LatexBlock(source)
            self._dirty = True


def sample_document() -> BlockDocument:
    blocks: List[Block] = [
        TextBlock(
            "# GTKV block editor\n"
            "Navigate blocks with j/k, open a text block with Enter.\n"
            "Blocks are separate; no inline mixing.\n"
        )
    ]

    blocks.extend(
        [
            TextBlock(
                "# Editing\n"
                "Enter opens a temp file in Vim inside your terminal.\n"
                "Exit Vim to refresh the block content.\n"
            ),
            TextBlock(
                "# Python renders\n"
                "Python blocks render to SVG via __gtkv__.renderer.\n"
                "They are rendered at runtime for export.\n"
            ),
            PythonImageBlock(
                "import matplotlib.pyplot as plt\n"
                "\n"
                "fig, ax = plt.subplots()\n"
                "ax.plot([0, 1, 2], [0, 1, 0.5])\n"
                "ax.set_title(\"Sample plot\")\n"
                "fig.savefig(__gtkv__.renderer, format=\"svg\", dpi=200, transparent=True, bbox_inches=\"tight\")\n",
                format="svg",
            ),
            LatexBlock(
                r"\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}"
            ),
            TextBlock(
                "# Notes\n"
                "- No inline mixing; each block is its own unit.\n"
                "- Vim runs externally; GTK stays focused on layout.\n"
            ),
            ThreeBlock(default_three_template()),
        ]
    )

    return BlockDocument(blocks)
