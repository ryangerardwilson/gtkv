"""Document model as source of truth for text + images."""
from __future__ import annotations

from collections.abc import Callable

from editor_segments import ImageSegment, Segment, TextSegment


class DocumentModel:
    def __init__(self, segments: list[Segment] | None = None) -> None:
        self._segments: list[Segment] = segments or [TextSegment("")]
        self._selection_start: int | None = None
        self._selection_end: int | None = None
        self._listeners: list[Callable[["DocumentModel"], None]] = []

    def add_listener(self, listener: Callable[["DocumentModel"], None]) -> None:
        self._listeners.append(listener)

    def set_segments(self, segments: list[Segment]) -> None:
        self._segments = segments or [TextSegment("")]
        self.clear_selection()
        self._notify()

    def get_segments(self) -> list[Segment]:
        return list(self._segments)

    def get_selection(self) -> tuple[int | None, int | None]:
        return self._selection_start, self._selection_end

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

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener(self)
