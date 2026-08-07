from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse


ALLOWED_RICH_TEXT_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li",
    "blockquote", "a", "hr", "code", "pre", "span",
}
SELF_CLOSING_TAGS = {"br", "hr"}
ALLOWED_LINK_SCHEMES = {"http", "https", "mailto"}


def _is_allowed_href(value: str) -> bool:
    cleaned = value.strip()
    if not cleaned:
        return False
    return urlparse(cleaned).scheme.lower() in ALLOWED_LINK_SCHEMES


class _RichHtmlSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.open_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized not in ALLOWED_RICH_TEXT_TAGS:
            return
        if normalized in SELF_CLOSING_TAGS:
            self.parts.append(f"<{normalized}>")
            return
        rendered_attrs: list[str] = []
        if normalized == "a":
            attr_map = {name.lower(): value for name, value in attrs if value is not None}
            href = attr_map.get("href", "")
            if _is_allowed_href(href):
                rendered_attrs.append(f'href="{escape(href, quote=True)}"')
                title = attr_map.get("title", "").strip()
                if title:
                    rendered_attrs.append(f'title="{escape(title, quote=True)}"')
                rendered_attrs.append('target="_blank"')
                rendered_attrs.append('rel="noopener noreferrer"')
        attrs_text = f" {' '.join(rendered_attrs)}" if rendered_attrs else ""
        self.parts.append(f"<{normalized}{attrs_text}>")
        self.open_tags.append(normalized)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized not in ALLOWED_RICH_TEXT_TAGS or normalized in SELF_CLOSING_TAGS:
            return
        if normalized not in self.open_tags:
            return
        while self.open_tags:
            current = self.open_tags.pop()
            self.parts.append(f"</{current}>")
            if current == normalized:
                break

    def handle_data(self, data: str) -> None:
        self.parts.append(escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def get_html(self) -> str:
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        return "".join(self.parts).strip()


def sanitize_rich_html(value: str) -> str:
    parser = _RichHtmlSanitizer()
    parser.feed(value or "")
    parser.close()
    return parser.get_html()
