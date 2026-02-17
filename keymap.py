"""Keymap configuration and matching."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, cast

import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk  # type: ignore[import-not-found, attr-defined]

import config


DEFAULT_LEADER = ","

_SPECIAL_KEYVAL_TO_TOKEN: dict[int, str] = {
    Gdk.KEY_Escape: "<Esc>",
    Gdk.KEY_Return: "<CR>",
    Gdk.KEY_KP_Enter: "<CR>",
    Gdk.KEY_Tab: "<Tab>",
    Gdk.KEY_BackSpace: "<BS>",
    Gdk.KEY_Up: "<Up>",
    Gdk.KEY_Down: "<Down>",
    Gdk.KEY_Left: "<Left>",
    Gdk.KEY_Right: "<Right>",
    Gdk.KEY_Home: "<Home>",
    Gdk.KEY_End: "<End>",
    Gdk.KEY_Page_Up: "<PageUp>",
    Gdk.KEY_Page_Down: "<PageDown>",
}

_SPECIAL_TOKENS = set(_SPECIAL_KEYVAL_TO_TOKEN.values())

_DISPLAY_TOKENS: dict[str, str] = {
    "<Esc>": "Esc",
    "<CR>": "Enter",
    "<Tab>": "Tab",
    "<BS>": "Backspace",
    "<Up>": "Up",
    "<Down>": "Down",
    "<Left>": "Left",
    "<Right>": "Right",
    "<Home>": "Home",
    "<End>": "End",
    "<PageUp>": "PageUp",
    "<PageDown>": "PageDown",
}


DEFAULT_KEYMAP: dict[str, Any] = {
    "leader": DEFAULT_LEADER,
    "modes": {
        "document": {
            "move_down": "j",
            "move_up": "k",
            "move_block_down": "<C-j>",
            "move_block_up": "<C-k>",
            "first_block": "gg",
            "last_block": "G",
            "open_editor": "<CR>",
            "quit_no_save": "q",
            "export_html": "<C-e>",
            "help_toggle": "?",
            "paste_block": "p",
            "delete_block": "dd",
            "yank_block": "yy",
            "toggle_theme": "<leader>m",
            "open_vault": "<leader>v",
            "open_toc": "<leader>i",
            "insert_text": "<leader>bn",
            "insert_title": "<leader>bht",
            "insert_h1": "<leader>bh1",
            "insert_h2": "<leader>bh2",
            "insert_h3": "<leader>bh3",
            "insert_toc": "<leader>bi",
            "insert_three": "<leader>bjs",
            "insert_pyimage": "<leader>bpy",
            "insert_latex": "<leader>bltx",
            "insert_map": "<leader>bmap",
        },
        "toc": {
            "move_down": "j",
            "move_up": "k",
            "collapse_or_parent": "h",
            "expand_or_child": "l",
            "open": "<CR>",
            "close": "<Esc>",
            "help_toggle": "?",
            "expand_all": "<leader>xar",
            "toggle_selected": "<leader>xr",
            "collapse_all": "<leader>xc",
        },
        "vault": {
            "move_down": "j",
            "move_up": "k",
            "up": "h",
            "enter_or_open": "l",
            "close": "<Esc>",
            "copy": "yy",
            "cut": "dd",
            "paste": "p",
            "new_entry": "<leader>n",
            "rename": "<leader>rn",
            "toggle_theme": "<leader>m",
        },
        "help": {
            "scroll_down": "j",
            "scroll_up": "k",
            "close": "?",
        },
    },
}


_HELP_SECTIONS = [
    (
        "Navigation",
        [
            {"type": "pair", "mode": "document", "a": "move_down", "b": "move_up", "label": "move selection"},
            {"type": "pair", "mode": "document", "a": "move_block_down", "b": "move_block_up", "label": "move block"},
            {"type": "pair", "mode": "document", "a": "first_block", "b": "last_block", "label": "first/last block"},
            {"type": "single", "mode": "document", "a": "open_toc", "label": "index drill"},
            {"type": "single", "mode": "document", "a": "open_vault", "label": "vault"},
            {"type": "single", "mode": "document", "a": "help_toggle", "label": "help"},
            {"type": "single", "mode": "document", "a": "toggle_theme", "label": "toggle theme"},
            {"type": "single", "mode": "document", "a": "delete_block", "label": "cut selected block"},
            {"type": "single", "mode": "document", "a": "yank_block", "label": "yank selected block"},
            {"type": "single", "mode": "document", "a": "paste_block", "label": "paste clipboard block"},
            {"type": "single", "mode": "document", "a": "open_editor", "label": "edit selected block"},
            {"type": "single", "mode": "document", "a": "quit_no_save", "label": "quit"},
        ],
    ),
    (
        "Vault",
        [
            {"type": "pair", "mode": "vault", "a": "move_down", "b": "move_up", "label": "move selection"},
            {"type": "pair", "mode": "vault", "a": "up", "b": "enter_or_open", "label": "up/enter"},
            {"type": "single", "mode": "vault", "a": "new_entry", "label": "new file/dir"},
            {"type": "single", "mode": "vault", "a": "rename", "label": "rename"},
            {"type": "single", "mode": "vault", "a": "copy", "label": "copy"},
            {"type": "single", "mode": "vault", "a": "cut", "label": "cut"},
            {"type": "single", "mode": "vault", "a": "paste", "label": "paste"},
            {"type": "single", "mode": "vault", "a": "close", "label": "back to document"},
        ],
    ),
    (
        "Blocks",
        [
            {"type": "single", "mode": "document", "a": "insert_text", "label": "normal text"},
            {"type": "single", "mode": "document", "a": "insert_title", "label": "title"},
            {
                "type": "multi",
                "mode": "document",
                "actions": ["insert_h1", "insert_h2", "insert_h3"],
                "label": "headings",
            },
            {"type": "single", "mode": "document", "a": "insert_toc", "label": "index"},
            {"type": "single", "mode": "document", "a": "insert_three", "label": "Three.js block"},
            {"type": "single", "mode": "document", "a": "insert_pyimage", "label": "Python render"},
            {"type": "single", "mode": "document", "a": "insert_latex", "label": "LaTeX block"},
            {"type": "single", "mode": "document", "a": "insert_map", "label": "map block"},
        ],
    ),
    (
        "Other",
        [
            {"type": "single", "mode": "document", "a": "export_html", "label": "export html"},
            {"type": "single", "mode": "document", "a": "help_toggle", "label": "toggle this help"},
        ],
    ),
]


def _is_printable_ascii(value: str) -> bool:
    return all(32 <= ord(ch) <= 126 for ch in value)


def _is_valid_leader(leader: str | None) -> bool:
    if leader is None or not isinstance(leader, str):
        return False
    if len(leader) != 1:
        return False
    if not _is_printable_ascii(leader):
        return False
    if leader in {"\t", "\n", "\r"}:
        return False
    return True


def _normalize_special(name: str) -> str | None:
    lookup = {
        "esc": "<Esc>",
        "escape": "<Esc>",
        "cr": "<CR>",
        "enter": "<CR>",
        "tab": "<Tab>",
        "bs": "<BS>",
        "backspace": "<BS>",
        "up": "<Up>",
        "down": "<Down>",
        "left": "<Left>",
        "right": "<Right>",
        "home": "<Home>",
        "end": "<End>",
        "pageup": "<PageUp>",
        "pagedown": "<PageDown>",
    }
    return lookup.get(name.lower())


def _normalize_token(token: str) -> str | None:
    if token.lower() == "leader":
        return "<leader>"
    special = _normalize_special(token)
    if special:
        return special
    if token.lower().startswith(("c-", "a-", "s-")):
        modifier = token[0].upper()
        base = token[2:]
        if len(base) == 1 and _is_printable_ascii(base):
            return f"<{modifier}-{base.lower()}>"
        base_special = _normalize_special(base)
        if base_special is not None:
            base_name = base_special.strip("<>")
            return f"<{modifier}-{base_name}>"
        return None
    return None


def parse_sequence(value: str) -> list[str] | None:
    if not isinstance(value, str):
        return None
    if not value:
        return None
    tokens: list[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "<":
            end = value.find(">", i + 1)
            if end == -1:
                if _is_printable_ascii(ch):
                    tokens.append(ch)
                i += 1
                continue
            raw = value[i + 1 : end]
            normalized = _normalize_token(raw)
            if normalized is None:
                return None
            tokens.append(normalized)
            i = end + 1
            continue
        if not _is_printable_ascii(ch):
            return None
        tokens.append(ch)
        i += 1
    return tokens


def _expand_leader(tokens: list[str], leader: str) -> list[str] | None:
    expanded: list[str] = []
    for token in tokens:
        if token == "<leader>":
            if not _is_valid_leader(leader):
                return None
            expanded.append(leader)
        else:
            expanded.append(token)
    return expanded


def _validate_tokens(tokens: list[str]) -> bool:
    if not tokens:
        return False
    if len(tokens) > 6:
        return False
    for token in tokens:
        if token == "<leader>":
            return False
        if token in _SPECIAL_TOKENS:
            continue
        if token.startswith("<") and token.endswith(">"):
            inner = token[1:-1]
            if len(inner) < 3:
                return False
            modifier = inner[0]
            if modifier not in {"C", "A", "S"}:
                return False
            if inner[1] != "-":
                return False
            base = inner[2:]
            if len(base) == 1 and _is_printable_ascii(base):
                continue
            if _normalize_special(base) is not None:
                continue
            return False
        if len(token) != 1:
            return False
        if not _is_printable_ascii(token):
            return False
    return True


def _merge_keymap_defaults(data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    changed = False
    merged = {
        "leader": DEFAULT_KEYMAP["leader"],
        "modes": {},
    }
    leader: str | None = data.get("leader") if isinstance(data, dict) else None
    if _is_valid_leader(leader):
        merged["leader"] = leader
    elif leader is not None:
        changed = True
    modes = data.get("modes") if isinstance(data, dict) else None
    default_modes = cast(dict[str, dict[str, str]], DEFAULT_KEYMAP["modes"])
    for mode, defaults in default_modes.items():
        merged_mode: dict[str, str] = {}
        existing = modes.get(mode) if isinstance(modes, dict) else None
        for action, default_sequences in defaults.items():
            sequence = default_sequences
            if isinstance(existing, dict) and action in existing:
                candidate = existing.get(action)
                if isinstance(candidate, str):
                    sequence = candidate
                elif isinstance(candidate, list) and candidate:
                    first = candidate[0]
                    if isinstance(first, str):
                        sequence = first
                        changed = True
                    else:
                        changed = True
                else:
                    changed = True
            merged_mode[action] = sequence
        merged["modes"][mode] = merged_mode
    if data != merged:
        changed = True
    return merged, changed


def _normalize_sequence(leader: str, sequence: str) -> tuple[str, ...] | None:
    tokens = parse_sequence(sequence)
    if tokens is None:
        return None
    expanded = _expand_leader(tokens, leader)
    if expanded is None:
        return None
    if not _validate_tokens(expanded):
        return None
    return tuple(expanded)


@dataclass
class Keymap:
    leader: str
    sequences: dict[str, dict[str, tuple[str, ...]]]
    matchers: dict[str, "KeyMatcher"]

    def match(self, mode: str, token: str) -> tuple[str | None, bool]:
        matcher = self.matchers.get(mode)
        if matcher is None:
            return None, False
        return matcher.process(token)

    def get_sequence(self, mode: str, action: str) -> tuple[str, ...] | None:
        return self.sequences.get(mode, {}).get(action)


class KeyMatcher:
    def __init__(self, sequences: dict[tuple[str, ...], str], timeout: float) -> None:
        self._sequences = sequences
        self._prefixes: set[tuple[str, ...]] = set()
        for seq in sequences:
            for i in range(1, len(seq)):
                self._prefixes.add(seq[:i])
        self._buffer: list[str] = []
        self._last_input = 0.0
        self._timeout = timeout

    def _expire(self) -> None:
        if self._buffer and time.monotonic() - self._last_input > self._timeout:
            self._buffer.clear()

    def process(self, token: str) -> tuple[str | None, bool]:
        self._expire()
        self._buffer.append(token)
        self._last_input = time.monotonic()
        current = tuple(self._buffer)
        if current in self._sequences:
            action = self._sequences[current]
            self._buffer.clear()
            return action, True
        if current in self._prefixes:
            return None, True
        self._buffer = [token]
        current = tuple(self._buffer)
        if current in self._sequences:
            action = self._sequences[current]
            self._buffer.clear()
            return action, True
        if current in self._prefixes:
            return None, True
        self._buffer.clear()
        return None, False


def event_to_token(keyval: int, state: int) -> str | None:
    if state & Gdk.ModifierType.SUPER_MASK:
        return None
    ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
    alt_mask = getattr(Gdk.ModifierType, "ALT_MASK", None)
    if alt_mask is None:
        alt_mask = getattr(Gdk.ModifierType, "MOD1_MASK", 0)
    alt = bool(state & alt_mask) if alt_mask else False
    shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
    if ctrl and alt:
        return None
    if keyval in _SPECIAL_KEYVAL_TO_TOKEN:
        token = _SPECIAL_KEYVAL_TO_TOKEN[keyval]
    elif 32 <= keyval <= 126:
        token = chr(keyval)
    else:
        return None
    if ctrl or alt:
        if shift:
            return None
        if token in _SPECIAL_TOKENS:
            return None
        base = token
        if len(base) == 1 and base.isalpha():
            base = base.lower()
        modifier = "C" if ctrl else "A"
        return f"<{modifier}-{base}>"
    return token


def _sequence_display(tokens: tuple[str, ...], leader: str) -> str:
    parts: list[str] = []
    for token in tokens:
        if token == " ":
            parts.append("Space")
            continue
        if token in _DISPLAY_TOKENS:
            parts.append(_DISPLAY_TOKENS[token])
            continue
        if token.startswith("<") and token.endswith(">"):
            inner = token[1:-1]
            if inner.startswith("C-"):
                base = inner[2:]
                parts.append(f"Ctrl+{base.upper()}")
                continue
            if inner.startswith("A-"):
                base = inner[2:]
                parts.append(f"Alt+{base.upper()}")
                continue
            if inner.startswith("S-"):
                base = inner[2:]
                parts.append(f"Shift+{base.upper()}")
                continue
            parts.append(inner)
            continue
        parts.append(token)
    if all(len(part) == 1 for part in parts):
        return "".join(parts)
    return " ".join(parts)


def _primary_sequence(keymap: Keymap, mode: str, action: str) -> tuple[str, ...] | None:
    return keymap.get_sequence(mode, action)


def build_help_lines(keymap: Keymap) -> list[str]:
    lines: list[str] = []
    for title, items in _HELP_SECTIONS:
        lines.append(title)
        for item in items:
            kind = item["type"]
            if kind == "single":
                seq = _primary_sequence(keymap, item["mode"], item["a"])
                if seq is None:
                    continue
                keys = _sequence_display(seq, keymap.leader)
                lines.append(f"  {keys:10} {item['label']}")
            elif kind == "pair":
                seq_a = _primary_sequence(keymap, item["mode"], item["a"])
                seq_b = _primary_sequence(keymap, item["mode"], item["b"])
                if seq_a is None or seq_b is None:
                    continue
                keys = f"{_sequence_display(seq_a, keymap.leader)}/{_sequence_display(seq_b, keymap.leader)}"
                lines.append(f"  {keys:10} {item['label']}")
            elif kind == "multi":
                keys_list = []
                for action in item["actions"]:
                    seq = _primary_sequence(keymap, item["mode"], action)
                    if seq is not None:
                        keys_list.append(_sequence_display(seq, keymap.leader))
                if not keys_list:
                    continue
                keys = " ".join(keys_list)
                lines.append(f"  {keys:10} {item['label']}")
        lines.append("")
    if lines and not lines[-1]:
        lines.pop()
    return lines


def load_keymap() -> Keymap:
    raw_config = config.load_config()
    raw_keymap = raw_config.get("keymap") if isinstance(raw_config, dict) else None
    merged, changed = _merge_keymap_defaults(raw_keymap or {})
    leader = merged["leader"]
    if not _is_valid_leader(leader):
        leader = DEFAULT_LEADER
        merged["leader"] = leader
        changed = True
    sequences: dict[str, dict[str, tuple[str, ...]]] = {}
    default_modes = cast(dict[str, dict[str, str]], DEFAULT_KEYMAP["modes"])
    for mode, actions in merged["modes"].items():
        sequences[mode] = {}
        for action, raw_sequences in actions.items():
            normalized = _normalize_sequence(leader, raw_sequences)
            if normalized is None:
                default_sequence = default_modes[mode][action]
                normalized = _normalize_sequence(leader, default_sequence)
                changed = True
            if normalized is None:
                continue
            sequences[mode][action] = normalized
    matchers: dict[str, KeyMatcher] = {}
    for mode, actions in sequences.items():
        seq_map: dict[tuple[str, ...], str] = {}
        for action, seq in actions.items():
            if seq in seq_map:
                continue
            seq_map[seq] = action
        matchers[mode] = KeyMatcher(seq_map, timeout=2.0)
    if changed:
        raw_config = raw_config if isinstance(raw_config, dict) else {}
        raw_config["keymap"] = merged
        config.save_config(raw_config)
    return Keymap(leader=leader, sequences=sequences, matchers=matchers)
