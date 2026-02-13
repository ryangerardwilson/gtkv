from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

from block_model import BlockDocument, LatexBlock, PythonImageBlock, TextBlock, ThreeBlock


SCHEMA_VERSION = 4


def load_document(path: Path) -> BlockDocument:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_schema(conn)
        blocks = []
        for row in conn.execute(
            "SELECT id, position, type, text, image_id, format, rendered_data, rendered_hash, error "
            "FROM blocks ORDER BY position"
        ):
            if row["type"] == "text":
                blocks.append(TextBlock(row["text"] or ""))
                continue
            if row["type"] == "three":
                blocks.append(ThreeBlock(row["text"] or ""))
            if row["type"] == "pyimage":
                rendered_path = _materialize_pyimage(
                    path,
                    row["rendered_data"],
                    row["format"],
                    row["rendered_hash"],
                )
                blocks.append(
                    PythonImageBlock(
                        row["text"] or "",
                        format=row["format"] or "png",
                        rendered_data=row["rendered_data"],
                        rendered_hash=row["rendered_hash"],
                        last_error=row["error"],
                        rendered_path=rendered_path,
                    )
                )
            if row["type"] == "latex":
                blocks.append(LatexBlock(row["text"] or ""))
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
            elif isinstance(block, ThreeBlock):
                conn.execute(
                    "INSERT INTO blocks (position, type, text) VALUES (?, 'three', ?)",
                    (position, block.source),
                )
            elif isinstance(block, PythonImageBlock):
                conn.execute(
                    """
                    INSERT INTO blocks
                        (position, type, text, format, rendered_data, rendered_hash, error)
                    VALUES
                        (?, 'pyimage', ?, ?, ?, ?, ?)
                    """,
                    (
                        position,
                        block.source,
                        block.format,
                        block.rendered_data,
                        block.rendered_hash,
                        block.last_error,
                    ),
                )
            elif isinstance(block, LatexBlock):
                conn.execute(
                    "INSERT INTO blocks (position, type, text) VALUES (?, 'latex', ?)",
                    (position, block.source),
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
            type TEXT NOT NULL CHECK(type IN ('text','three','pyimage','latex')),
            text TEXT,
            image_id INTEGER,
            format TEXT,
            rendered_data TEXT,
            rendered_hash TEXT,
            error TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blocks_position ON blocks(position)")

    current_version = _get_schema_version(conn)
    if current_version < SCHEMA_VERSION:
        _migrate_schema(conn, current_version)


def _upsert_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _get_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        return 0
    try:
        return int(row["value"])
    except (ValueError, TypeError):
        return 0


def _migrate_schema(conn: sqlite3.Connection, current_version: int) -> None:
    if current_version < 2:
        conn.execute("ALTER TABLE blocks RENAME TO blocks_old")
        conn.execute(
            """
            CREATE TABLE blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position INTEGER NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('text','image','three')),
                text TEXT,
                image_id INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO blocks (id, position, type, text, image_id, created_at, updated_at)
            SELECT id, position, type, text, image_id, created_at, updated_at
            FROM blocks_old
            """
        )
        conn.execute("DROP TABLE blocks_old")

    if current_version < 3:
        conn.execute("ALTER TABLE blocks RENAME TO blocks_old")
        conn.execute(
            """
            CREATE TABLE blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position INTEGER NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('text','image','three','pyimage')),
                text TEXT,
                image_id INTEGER,
                format TEXT,
                rendered_data TEXT,
                rendered_hash TEXT,
                error TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO blocks (id, position, type, text, image_id, created_at, updated_at)
            SELECT id, position, type, text, image_id, created_at, updated_at
            FROM blocks_old
            """
        )
        conn.execute("DROP TABLE blocks_old")

    if current_version < 4:
        conn.execute("ALTER TABLE blocks RENAME TO blocks_old")
        conn.execute(
            """
            CREATE TABLE blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position INTEGER NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('text','three','pyimage','latex')),
                text TEXT,
                image_id INTEGER,
                format TEXT,
                rendered_data TEXT,
                rendered_hash TEXT,
                error TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO blocks (id, position, type, text, image_id, format, rendered_data, rendered_hash, error, created_at, updated_at)
            SELECT id, position, type, text, image_id, format, rendered_data, rendered_hash, error, created_at, updated_at
            FROM blocks_old
            WHERE type IN ('text','three','pyimage','latex')
            """
        )
        conn.execute("DROP TABLE blocks_old")

    _upsert_meta(conn, "schema_version", str(SCHEMA_VERSION))


def _materialize_pyimage(
    doc_path: Path,
    rendered_data: str | None,
    render_format: str | None,
    rendered_hash: str | None,
) -> str | None:
    if not rendered_data:
        return None
    cache_dir = _cache_root_for_document(doc_path) / "pyimage"
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest_source = rendered_hash or rendered_data
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:16]
    extension = ".svg"
    image_path = cache_dir / f"pyimage-{digest}{extension}"
    try:
        image_path.write_text(rendered_data, encoding="utf-8")
    except (OSError, ValueError):
        return None
    return image_path.as_posix()


def _cache_root_for_document(path: Path) -> Path:
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    digest = hashlib.sha256(path.as_posix().encode("utf-8")).hexdigest()[:16]
    return cache_root / "gtkv" / "sqlite" / digest
