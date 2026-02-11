"""HTML persistence for GTKV documents."""

from __future__ import annotations

import html
from html.parser import HTMLParser

from editor_segments import ImageSegment, Segment, TextSegment


def build_html(segments: list[Segment]) -> str:
    body_parts: list[str] = []
    for segment in segments:
        if isinstance(segment, TextSegment):
            escaped = html.escape(segment.text)
            body_parts.append(f'<pre class="text">{escaped}</pre>')
        elif isinstance(segment, ImageSegment):
            escaped_alt = html.escape(segment.alt)
            body_parts.append(f'<img src="{segment.data_uri}" alt="{escaped_alt}" />')
    body = "\n".join(body_parts)
    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        '  <meta charset="utf-8" />\n'
        "  <title>GTKV Document</title>\n"
        "  <style>body{font-family:monospace;white-space:normal;}"
        "pre.text{font-family:monospace;white-space:pre-wrap;}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def parse_html(html_text: str) -> list[Segment]:
    parser = _GTKVHTMLParser()
    parser.feed(html_text)
    segments = parser.segments
    if not segments:
        return [TextSegment("")]
    return segments


class _GTKVHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.segments: list[Segment] = []
        self._in_pre = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "pre":
            self._in_pre = True
        if tag == "img":
            attrs_dict = {key: value for key, value in attrs}
            src = attrs_dict.get("src")
            if src:
                alt = attrs_dict.get("alt") or ""
                self.segments.append(ImageSegment(src, alt))

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre":
            self._in_pre = False

    def handle_data(self, data: str) -> None:
        if self._in_pre and data:
            self.segments.append(TextSegment(data))
