from __future__ import annotations

from html.parser import HTMLParser


class PageParser(HTMLParser):
    """Collects the on-page signals the checks need, using only the stdlib."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.lang: str | None = None
        self.canonical: str | None = None
        self.meta: dict[str, str] = {}
        self.h1_count = 0
        self.img_total = 0
        self.img_missing_alt = 0
        self.script_count = 0
        self.blocking_scripts = 0
        self.jsonld_blocks = 0
        self.http_resources: list[str] = []
        self.links: list[str] = []
        self._in_head = False
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "head":
            self._in_head = True
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key and "content" in a:
                self.meta[key] = a["content"] or ""
        elif tag == "link":
            rel = (a.get("rel") or "").lower().split()
            href = a.get("href") or ""
            if "canonical" in rel:
                self.canonical = href
            elif ("stylesheet" in rel or "icon" in rel) and href.startswith("http://"):
                self.http_resources.append(href)
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "img":
            self.img_total += 1
            if a.get("alt") is None:
                self.img_missing_alt += 1
            if (a.get("src") or "").startswith("http://"):
                self.http_resources.append(a["src"])
        elif tag == "script":
            self.script_count += 1
            src = a.get("src") or ""
            if (a.get("type") or "").lower() == "application/ld+json":
                self.jsonld_blocks += 1
            if src.startswith("http://"):
                self.http_resources.append(src)
            if (
                self._in_head
                and src
                and "async" not in a
                and "defer" not in a
                and (a.get("type") or "").lower() != "module"
            ):
                self.blocking_scripts += 1
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "head":
            self._in_head = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
