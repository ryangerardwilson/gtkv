from __future__ import annotations

import hashlib
import mimetypes
import os
import sqlite3
from pathlib import Path

from block_model import BlockDocument, ImageBlock, TextBlock


SCHEMA_VERSION = 1


def load_document(path: Path) -> BlockDocument:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_schema(conn)
        blocks = []
        for row in conn.execute(
            "SELECT id, position, type, text, image_id FROM blocks ORDER BY position"
        ):
            if row["type"] == "text":
                blocks.append(TextBlock(row["text"] or ""))
                continue
            if row["type"] == "image" and row["image_id"] is not None:
                image_row = conn.execute(
                    "SELECT id, mime, data, alt FROM images WHERE id = ?",
                    (row["image_id"],),
                ).fetchone()
                if image_row is None:
                    continue
                cache_path = _materialize_image(
                    path, image_row["id"], image_row["mime"], image_row["data"]
                )
                blocks.append(
                    ImageBlock(
                        cache_path,
                        alt=image_row["alt"] or "",
                        data=image_row["data"],
                        mime=image_row["mime"],
                    )
                )
        doc = BlockDocument(blocks, path=path)
        doc.clear_dirty()
        return doc
    finally:
        conn.close()


def save_document(path: Path, document: BlockDocument) -> None:
    conn = sqlite3.connect(path)
    try:
        _ensure_schema(conn)
        conn.execute("BEGIN")
        conn.execute("DELETE FROM blocks")
        conn.execute("DELETE FROM images")

        position = 0
        for block in document.blocks:
            if isinstance(block, TextBlock):
                conn.execute(
                    "INSERT INTO blocks (position, type, text) VALUES (?, 'text', ?)",
                    (position, block.text),
                )
            elif isinstance(block, ImageBlock):
                image_bytes, mime = _resolve_image_payload(block)
                if image_bytes is None or mime is None:
                    position += 1
                    continue
                cursor = conn.execute(
                    "INSERT INTO images (mime, data, alt) VALUES (?, ?, ?)",
                    (mime, image_bytes, block.alt),
                )
                image_id = cursor.lastrowid
                conn.execute(
                    "INSERT INTO blocks (position, type, image_id) VALUES (?, 'image', ?)",
                    (position, image_id),
                )
            position += 1

        _upsert_meta(conn, "schema_version", str(SCHEMA_VERSION))
        conn.commit()
        document.set_path(path)
        document.clear_dirty()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mime TEXT NOT NULL,
            data BLOB NOT NULL,
            alt TEXT DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            position INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('text','image')),
            text TEXT,
            image_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blocks_position ON blocks(position)")


def _upsert_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _resolve_image_payload(block: ImageBlock) -> tuple[bytes | None, str | None]:
    if block.data and block.mime:
        return block.data, block.mime
    if block.path and os.path.exists(block.path):
        try:
            image_bytes = Path(block.path).read_bytes()
        except OSError:
            return None, None
        mime, _ = mimetypes.guess_type(block.path)
        return image_bytes, mime or "application/octet-stream"
    return None, None


def _materialize_image(doc_path: Path, image_id: int, mime: str, data: bytes) -> str:
    cache_dir = _cache_root_for_document(doc_path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    extension = mimetypes.guess_extension(mime or "") or ".img"
    filename = f"image-{image_id}{extension}"
    image_path = cache_dir / filename
    if not image_path.exists():
        image_path.write_bytes(data)
    return image_path.as_posix()


def _cache_root_for_document(path: Path) -> Path:
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    digest = hashlib.sha256(path.as_posix().encode("utf-8")).hexdigest()[:16]
    return cache_root / "gtkv" / "sqlite" / digest
