"""Segment model for serialized document content."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextSegment:
    text: str


@dataclass(frozen=True)
class ImageSegment:
    data_uri: str
    alt: str


Segment = TextSegment | ImageSegment
