from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

import config
from design_constants import colors_for
from three_template import default_three_template


@dataclass(frozen=True)
class TextBlock:
    text: str
    kind: str = "body"


@dataclass(frozen=True)
class ThreeBlock:
    source: str
    title: str = ""


@dataclass(frozen=True)
class PythonImageBlock:
    source: str
    format: str = "svg"
    rendered_data_dark: str | None = None
    rendered_hash_dark: str | None = None
    rendered_path_dark: str | None = None
    rendered_data_light: str | None = None
    rendered_hash_light: str | None = None
    rendered_path_light: str | None = None
    last_error: str | None = None


@dataclass(frozen=True)
class LatexBlock:
    source: str


@dataclass(frozen=True)
class MapBlock:
    source: str


Block = TextBlock | ThreeBlock | PythonImageBlock | LatexBlock | MapBlock


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

    def move_block(self, from_index: int, to_index: int) -> bool:
        if from_index < 0 or from_index >= len(self._blocks):
            return False
        if to_index < 0 or to_index >= len(self._blocks):
            return False
        if from_index == to_index:
            return False
        block = self._blocks.pop(from_index)
        self._blocks.insert(to_index, block)
        self._dirty = True
        return True

    def remove_block(self, index: int) -> Block | None:
        if index < 0 or index >= len(self._blocks):
            return None
        block = self._blocks.pop(index)
        self._dirty = True
        return block

    def remove_text_blocks_by_kind(self, kind: str) -> None:
        original_len = len(self._blocks)
        self._blocks = [
            block
            for block in self._blocks
            if not (isinstance(block, TextBlock) and block.kind == kind)
        ]
        if len(self._blocks) != original_len:
            self._dirty = True

    def set_text_block(self, index: int, text: str) -> None:
        if index < 0 or index >= len(self._blocks):
            return
        block = self._blocks[index]
        if isinstance(block, TextBlock):
            self._blocks[index] = TextBlock(text, kind=block.kind)
            self._dirty = True

    def set_text_block_kind(self, index: int, kind: str) -> None:
        if index < 0 or index >= len(self._blocks):
            return
        block = self._blocks[index]
        if isinstance(block, TextBlock):
            self._blocks[index] = TextBlock(block.text, kind=kind)
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
                rendered_data_dark=None,
                rendered_hash_dark=None,
                rendered_path_dark=None,
                rendered_data_light=None,
                rendered_hash_light=None,
                rendered_path_light=None,
                last_error=None,
            )
            self._dirty = True

    def set_python_image_render(
        self,
        index: int,
        rendered_data_dark: str | None,
        rendered_hash_dark: str | None,
        rendered_data_light: str | None,
        rendered_hash_light: str | None,
        last_error: str | None,
    ) -> None:
        if index < 0 or index >= len(self._blocks):
            return
        block = self._blocks[index]
        if isinstance(block, PythonImageBlock):
            self._blocks[index] = PythonImageBlock(
                block.source,
                format=block.format,
                rendered_data_dark=rendered_data_dark,
                rendered_hash_dark=rendered_hash_dark,
                rendered_path_dark=None,
                rendered_data_light=rendered_data_light,
                rendered_hash_light=rendered_hash_light,
                rendered_path_light=None,
                last_error=last_error,
            )
            self._dirty = True

    def set_map_block(self, index: int, source: str) -> None:
        if index < 0 or index >= len(self._blocks):
            return
        block = self._blocks[index]
        if isinstance(block, MapBlock):
            self._blocks[index] = MapBlock(source)
            self._dirty = True

    def set_latex_block(self, index: int, source: str) -> None:
        if index < 0 or index >= len(self._blocks):
            return
        block = self._blocks[index]
        if isinstance(block, LatexBlock):
            self._blocks[index] = LatexBlock(source)
            self._dirty = True


def sample_document() -> BlockDocument:
    palette = colors_for(config.get_ui_mode() or "dark")
    blocks: List[Block] = [
        TextBlock(
            "Documentation Title",
            kind="title",
        ),
        TextBlock(
            "",
            kind="toc",
        ),
    ]

    blocks.extend(
        [
            TextBlock(
                "Navigation",
                kind="h1",
            ),
            TextBlock(
                "Use j/k to move between blocks.\n"
                "Press Enter to edit the selected block in Vim.\n"
                "Exit Vim to refresh the block content.\n"
                "Press ? to show the shortcuts panel.",
                kind="body",
            ),
            TextBlock(
                "Heading 1",
                kind="h1",
            ),
            TextBlock(
                "Heading 1 is for top-level sections.\n"
                "Use it to structure the document into major parts.",
                kind="body",
            ),
            TextBlock(
                "Heading 2",
                kind="h2",
            ),
            TextBlock(
                "You can structure documents with three heading levels.\n"
                "Use ,bh1, ,bh2, and ,bh3 for hierarchy.",
                kind="body",
            ),
            TextBlock(
                "Heading 3",
                kind="h3",
            ),
            TextBlock(
                "Heading 3 is useful for fine-grained sections.\n"
                "Use it sparingly for subtopics.",
                kind="body",
            ),
            TextBlock(
                "Three.js blocks",
                kind="h1",
            ),
            TextBlock(
                "Three.js blocks are JS modules with THREE, scene, camera,\n"
                "renderer, and canvas pre-wired.\n"
                "Use them for real-time 3D scenes.",
                kind="body",
            ),
            ThreeBlock(
                default_three_template(
                    config.get_ui_mode() or "dark", include_guidance=False
                )
            ),
            TextBlock(
                "LaTeX blocks",
                kind="h1",
            ),
            TextBlock(
                "LaTeX blocks render with KaTeX in a WebKit view.\n"
                "Edit the LaTeX source directly.",
                kind="body",
            ),
            LatexBlock(r"\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}"),
            TextBlock(
                "Map blocks",
                kind="h1",
            ),
            TextBlock(
                "Map blocks run Leaflet JS with L, map, and tileLayer globals.\n"
                "Use them to plot points, shapes, and paths on a dark basemap.",
                kind="body",
            ),
            MapBlock(
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
            ),
            TextBlock(
                "Python render blocks",
                kind="h1",
            ),
            TextBlock(
                "Python blocks render to SVG via __gtkv__.renderer.\n"
                "They are rendered at runtime for export.",
                kind="body",
            ),
            PythonImageBlock(
                "import matplotlib.pyplot as plt\n"
                "\n"
                "fig, ax = plt.subplots()\n"
                "ax.plot([0, 1, 2], [0, 1, 0.5])\n"
                'ax.set_title("Sample plot")\n'
                'fig.savefig(__gtkv__.renderer, format="svg", dpi=200, transparent=True, bbox_inches="tight")\n',
                format="svg",
            ),
            TextBlock(
                "Notes",
                kind="h3",
            ),
            TextBlock(
                "- No inline mixing; each block is its own unit.\n"
                "- Vim runs externally; GTK stays focused on layout.",
                kind="body",
            ),
        ]
    )

    return BlockDocument(blocks)
