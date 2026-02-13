"""Document loading and saving helpers."""

from __future__ import annotations

from pathlib import Path

from block_model import BlockDocument
from persistence_sqlite import load_document as load_sqlite
from persistence_sqlite import save_document as save_sqlite
from persistence_text import load_document as load_text
from persistence_text import save_document as save_text


TEXT_HEADER = "# GTKV v2"


def load(path: Path) -> BlockDocument:
    if _is_text_doc(path):
        return load_text(path)
    return load_sqlite(path)


def save(path: Path, document: BlockDocument) -> None:
    if _is_text_doc(path, check_header=False):
        save_text(path, document)
    else:
        save_sqlite(path, document)


def coerce_docv_path(path: Path) -> Path:
    if path.suffix == ".docv":
        return path
    return path.with_suffix(".docv")


def _is_text_doc(path: Path, check_header: bool = True) -> bool:
    if not check_header:
        return True
    try:
        with path.open("r", encoding="utf-8") as handle:
            first = handle.readline().strip()
    except OSError:
        return False
    return first == TEXT_HEADER
