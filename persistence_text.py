"""Text-based .docv persistence."""

from __future__ import annotations

from pathlib import Path

from block_model import BlockDocument, LatexBlock, PythonImageBlock, TextBlock, ThreeBlock


HEADER = "# GTKV v2"


def load_document(path: Path) -> BlockDocument:
    raw = path.read_text(encoding="utf-8")
    blocks = _parse_blocks(raw)
    doc = BlockDocument(blocks, path=path)
    doc.clear_dirty()
    return doc


def save_document(path: Path, document: BlockDocument) -> None:
    content = _serialize_blocks(document)
    path.write_text(content, encoding="utf-8")
    document.set_path(path)
    document.clear_dirty()


def _parse_blocks(raw: str) -> list:
    lines = raw.splitlines()
    if lines and lines[0].strip() == HEADER:
        lines = lines[1:]

    blocks = []
    current_type = None
    current_lines: list[str] = []
    current_meta: dict[str, str] = {}

    def _flush() -> None:
        nonlocal current_type, current_lines, current_meta
        if not current_type:
            current_lines = []
            current_meta = {}
            return
        content = "\n".join(current_lines).rstrip("\n")
        if current_type == "text":
            blocks.append(TextBlock(content))
        elif current_type == "three":
            blocks.append(ThreeBlock(content))
        elif current_type == "pyimage":
            fmt = current_meta.get("format", "svg")
            blocks.append(PythonImageBlock(content, format=fmt))
        elif current_type == "latex":
            blocks.append(LatexBlock(content))
        current_type = None
        current_lines = []
        current_meta = {}

    for line in lines:
        if line.startswith("::"):
            _flush()
            current_type = line[2:].strip()
            current_lines = []
            current_meta = {}
            continue
        if current_type == "pyimage" and ":" in line and not current_lines:
            key, value = line.split(":", 1)
            if key.strip() == "format":
                current_meta[key.strip()] = value.strip()
                continue
        current_lines.append(line)

    _flush()
    return blocks


def _serialize_blocks(document: BlockDocument) -> str:
    parts = [HEADER]
    for block in document.blocks:
        if isinstance(block, TextBlock):
            parts.append("::text")
            parts.append(block.text.rstrip("\n"))
            continue
        if isinstance(block, ThreeBlock):
            parts.append("::three")
            parts.append(block.source.rstrip("\n"))
            continue
        if isinstance(block, PythonImageBlock):
            parts.append("::pyimage")
            parts.append(f"format: {block.format}")
            parts.append(block.source.rstrip("\n"))
            continue
        if isinstance(block, LatexBlock):
            parts.append("::latex")
            parts.append(block.source.rstrip("\n"))
            continue
    return "\n".join(parts).rstrip("\n") + "\n"
