"""Export .gvim files to HTML without GTK."""

from __future__ import annotations

import sys
from pathlib import Path

import config
import document_io
from block_model import BlockDocument, get_document_title
from export_html import (
    build_index_link_id,
    build_index_tree_html,
    export_document,
    export_vault_index,
)


def _find_config_vault_for_path(path: Path) -> Path | None:
    vaults = [vault.resolve() for vault in config.get_vaults() if vault.exists()]
    if not vaults:
        return None
    resolved_path = path.resolve()
    for vault in vaults:
        if resolved_path == vault or vault in resolved_path.parents:
            return vault
    return None


def _run_export_all_for_root(root: Path) -> int:
    doc_paths = sorted(root.rglob("*.gvim"))
    if not doc_paths:
        print(f"No .gvim files found under {root}", file=sys.stderr)
        return 1
    python_path = _get_venv_python()
    ui_mode = config.get_ui_mode() or "dark"
    export_items: list[tuple[Path, BlockDocument, str | None]] = []
    index_items: list[tuple[Path, str | None]] = []
    for doc_path in doc_paths:
        document = document_io.load(doc_path)
        output_path = doc_path.with_suffix(".html")
        title = get_document_title(document)
        export_items.append((output_path, document, title))
        index_items.append((output_path, title))

    rel_index_items = [
        (path.relative_to(root), title or path.stem or path.name)
        for path, title in index_items
    ]

    for output_path, document, _title in export_items:
        rel_output = output_path.relative_to(root)
        depth = max(len(rel_output.parts) - 1, 0)
        base_prefix = "../" * depth
        index_href = f"{base_prefix}index.html#{build_index_link_id(rel_output)}"
        index_tree_html = build_index_tree_html(rel_index_items, base_prefix)
        export_document(
            document,
            output_path,
            python_path,
            ui_mode,
            index_tree_html=index_tree_html,
            index_href=index_href,
        )

    export_vault_index(root, index_items, ui_mode)
    return 0


def _get_venv_python() -> str | None:
    venv_python = Path.home() / ".gvim" / "venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return None


def main() -> int:
    root = _find_config_vault_for_path(Path.cwd())
    if root is None:
        print(
            "Export requires a configured vault. Run 'gvim init' in the vault root.",
            file=sys.stderr,
        )
        return 1
    return _run_export_all_for_root(root)


if __name__ == "__main__":
    raise SystemExit(main())
