"""Check local inline/reference Markdown links and heading/source-line anchors.

The supported Markdown subset is explicit: inline destinations without nested
parentheses, reference definitions, ATX headings and HTML id/name attributes.
"""
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


def markdown_text(text):
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s*(\x60{3,}|~{3,})", line)
        if match:
            marker = match[1][0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return "\n".join(lines)


def destinations(text):
    text = markdown_text(text)
    inline = re.findall(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^\s)]+)(?:\s+['\"][^'\"]*['\"])?\s*\)", text)
    references = re.findall(r"(?m)^\s{0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)", text)
    return [value[1:-1] if value.startswith("<") else value for value in inline + references]


def heading_anchors(text):
    text = markdown_text(text)
    class ExplicitAnchors(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.anchors = set()

        def handle_starttag(self, tag, attributes):
            for name, value in attributes:
                if value is not None and (name == "id" or tag == "a" and name == "name"):
                    self.anchors.add(value)

    parser = ExplicitAnchors()
    parser.feed(text)
    anchors = parser.anchors
    counts = {}
    for heading in re.findall(r"(?m)^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", text):
        heading = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
        heading = re.sub(r"<[^>]*>", "", unescape(heading)).lower()
        slug = "".join(c for c in heading if c.isalnum() or c in "_- " or c.isspace())
        slug = re.sub(r"\s", "-", slug)
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        anchors.add(slug if not count else f"{slug}-{count}")
    return anchors


def assert_onboarding_links(root, documents):
    root = Path(root).resolve(strict=True)
    for name in documents:
        source = (root / name).resolve(strict=True)
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError("onboarding source escapes checkout")
        for destination in destinations(source.read_text(encoding="utf-8")):
            url = urlsplit(destination)
            if url.scheme or url.netloc:
                continue
            target = (source.parent / unquote(url.path)).resolve() if url.path else source
            if not target.is_relative_to(root) or not target.exists():
                raise AssertionError(f"{name}: missing or escaping target {destination}")
            fragment = unquote(url.fragment)
            if not fragment:
                continue
            if not target.is_file():
                raise AssertionError(f"{name}: directory has no supported anchor {destination}")
            text = target.read_text(encoding="utf-8")
            if target.suffix.lower() in {".md", ".markdown", ".mdown", ".mkd"}:
                valid = fragment in heading_anchors(text)
            else:
                match = re.fullmatch(r"L([1-9][0-9]*)(?:-L([1-9][0-9]*))?", fragment)
                valid = bool(match and 1 <= int(match[1]) <= int(match[2] or match[1]) <= len(text.splitlines()))
            if not valid:
                raise AssertionError(f"{name}: missing anchor {destination}")
