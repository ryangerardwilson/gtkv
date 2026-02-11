"""Document model as source of truth for text + images."""

from __future__ import annotations

from collections.abc import Callable

from editor_segments import ImageSegment, Segment, TextSegment


class DocumentModel:
    def __init__(self, segments: list[Segment] | None = None) -> None:
        self._segments: list[Segment] = segments or [TextSegment("")]
        self._selection_start: int | None = None
        self._selection_end: int | None = None
        self._cursor_row: int = 0
        self._cursor_col: int = 0
        self._selection_anchor: tuple[int, int] | None = None
        self._selection_active: tuple[int, int] | None = None
        self._listeners: list[Callable[["DocumentModel"], None]] = []

    def add_listener(self, listener: Callable[["DocumentModel"], None]) -> None:
        self._listeners.append(listener)

    def set_segments(self, segments: list[Segment], notify: bool = True) -> None:
        self._segments = segments or [TextSegment("")]
        self.clear_selection()
        if notify:
            self._notify()

    def get_segments(self) -> list[Segment]:
        return list(self._segments)

    def get_cursor(self) -> tuple[int, int]:
        return self._cursor_row, self._cursor_col

    def get_selection(self) -> tuple[int | None, int | None]:
        return self._selection_start, self._selection_end

    def get_selection_span(
        self,
    ) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
        return self._selection_anchor, self._selection_active

    def set_text(self, text: str) -> None:
        self.set_segments([TextSegment(text)])

    def append_image(self, data_uri: str, alt: str) -> None:
        if not self._segments:
            self._segments = [TextSegment("")]
        self._segments.append(ImageSegment(data_uri, alt))
        self._notify()

    def set_selection(self, start: int, end: int) -> None:
        self._selection_start = start
        self._selection_end = end

    def clear_selection(self) -> None:
        self._selection_start = None
        self._selection_end = None
        self._selection_anchor = None
        self._selection_active = None

    def set_cursor(self, row: int, col: int) -> None:
        self._cursor_row = max(0, row)
        self._cursor_col = max(0, col)

    def move_cursor(self, dx: int, dy: int, extend_selection: bool = False) -> None:
        lines = self._get_text_lines()
        if not lines:
            self._cursor_row = 0
            self._cursor_col = 0
            return
        new_row = max(0, min(len(lines) - 1, self._cursor_row + dy))
        line_len = len(lines[new_row])
        new_col = max(0, min(line_len, self._cursor_col + dx))
        if extend_selection:
            if self._selection_anchor is None:
                self._selection_anchor = (self._cursor_row, self._cursor_col)
            self._selection_active = (new_row, new_col)
        else:
            self._selection_anchor = None
            self._selection_active = None
        self._cursor_row = new_row
        self._cursor_col = new_col

    def _get_text_lines(self) -> list[str]:
        parts: list[str] = []
        for segment in self._segments:
            if isinstance(segment, TextSegment):
                parts.append(segment.text)
        return "".join(parts).splitlines()

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener(self)
