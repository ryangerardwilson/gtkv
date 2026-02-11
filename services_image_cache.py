"""Image cache helpers for inline image data URIs."""

from __future__ import annotations

import base64
import hashlib
import os
import time
from pathlib import Path


def materialize_data_uri(data_uri: str) -> Path | None:
    if not data_uri.startswith("data:"):
        return None
    header, _, payload = data_uri.partition(",")
    if ";base64" not in header:
        return None
    mime = header[5:].split(";")[0] if header.startswith("data:") else ""
    ext = _extension_for_mime(mime)
    try:
        data = base64.b64decode(payload)
    except (ValueError, OSError):
        return None
    digest = hashlib.sha1(data).hexdigest()
    cache_root = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    cache_dir = Path(cache_root) / "n" / "inline-images"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    target = cache_dir / f"inline-{digest}.{ext}"
    if not target.exists():
        try:
            target.write_bytes(data)
        except OSError:
            return None
    else:
        try:
            os.utime(target, None)
        except OSError:
            pass
    return target


def cleanup_cache(max_days: int, max_bytes: int, max_files: int) -> None:
    cache_root = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    cache_dir = Path(cache_root) / "n" / "inline-images"
    if not cache_dir.exists():
        return

    try:
        entries = [
            entry
            for entry in cache_dir.iterdir()
            if entry.is_file() and entry.name.startswith("inline-")
        ]
    except OSError:
        return

    now = time.time()
    max_age = max_days * 86400

    def _stat(entry: Path) -> tuple[float, int]:
        try:
            stat = entry.stat()
            return stat.st_mtime, stat.st_size
        except OSError:
            return 0.0, 0

    for entry in entries:
        mtime, _size = _stat(entry)
        if max_age > 0 and now - mtime > max_age:
            try:
                entry.unlink()
            except OSError:
                pass

    try:
        entries = [
            entry
            for entry in cache_dir.iterdir()
            if entry.is_file() and entry.name.startswith("inline-")
        ]
    except OSError:
        return

    entries_with_stat: list[tuple[Path, float, int]] = []
    total_bytes = 0
    for entry in entries:
        mtime, size = _stat(entry)
        entries_with_stat.append((entry, mtime, size))
        total_bytes += size

    if (max_files and len(entries_with_stat) > max_files) or (
        max_bytes and total_bytes > max_bytes
    ):
        entries_with_stat.sort(key=lambda item: item[1])
        while entries_with_stat and (
            (max_files and len(entries_with_stat) > max_files)
            or (max_bytes and total_bytes > max_bytes)
        ):
            entry, _mtime, size = entries_with_stat.pop(0)
            try:
                entry.unlink()
            except OSError:
                pass
            total_bytes -= size


def _extension_for_mime(mime: str) -> str:
    mapping = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/gif": "gif",
        "image/bmp": "bmp",
        "image/webp": "webp",
    }
    return mapping.get(mime, "png")
