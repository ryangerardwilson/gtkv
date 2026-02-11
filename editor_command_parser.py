"""Command-line parser for Vim-style ex commands."""

from __future__ import annotations


def parse_ex_command(text: str) -> tuple[str, list[str]]:
    stripped = text.strip()
    if not stripped:
        return "", []
    parts = stripped.split()
    return parts[0], parts[1:]
