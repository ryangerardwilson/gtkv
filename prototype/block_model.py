from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


@dataclass(frozen=True)
class TextBlock:
    text: str


@dataclass(frozen=True)
class ImageBlock:
    path: str
    alt: str = ""


Block = TextBlock | ImageBlock


class BlockDocument:
    def __init__(self, blocks: Sequence[Block]) -> None:
        self._blocks: List[Block] = list(blocks)

    @property
    def blocks(self) -> List[Block]:
        return self._blocks

    def append_block(self, block: Block) -> None:
        self._blocks.append(block)


def sample_document(image_path: str | None) -> BlockDocument:
    blocks: List[Block] = [
        TextBlock(
            "# Prototype: Block-based editor\n"
            "This is a text block that would be backed by a terminal Vim instance.\n"
            "Text and images are separate blocks; no inline mixing.\n"
        )
    ]

    if image_path:
        blocks.append(ImageBlock(image_path, alt="Sample image"))

    blocks.extend(
        [
            TextBlock(
                "# Notes\n"
                "- Visual/block modes stay within a text block.\n"
                "- Images render as their own blocks.\n"
            ),
            TextBlock(
                "# Next\n"
                "Integrate a real Vim backend and map its grid into this block.\n"
            ),
        ]
    )

    return BlockDocument(blocks)
