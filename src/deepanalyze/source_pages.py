"""Identity-checked metadata from official arXiv and ACL landing pages."""
from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.parse import urlsplit

_HOSTS = {"arxiv.org", "www.arxiv.org", "aclanthology.org"}
_ARXIV = re.compile(r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?", re.I)
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def _clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _doi(value):
    value = _clean(value)
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value, flags=re.I).casefold()


def _arxiv(value):
    return re.sub(r"v\d+$", "", value, flags=re.I).casefold()


def _valid_url(value):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or parsed.hostname not in _HOSTS or parsed.port not in (None, 443)
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Unsupported source URL")
        return parsed
    except (ValueError, TypeError):
        raise ValueError("Unsupported source URL") from None


def _date(value):
    match = re.fullmatch(r"(\d{4})(?:[-/](\d{1,2}))?(?:[-/](\d{1,2}))?", _clean(value))
    if not match:
        return None
    year, month, day = match.groups()
    try:
        date(int(year), int(month or 1), int(day or 1))
    except ValueError:
        return None
    return year + (f"-{int(month):02d}" if month else "") + (f"-{int(day):02d}" if day else "")


class _Page(HTMLParser):
    def __init__(self, abstract_tag="div", abstract_class="acl-abstract"):
        super().__init__(convert_charrefs=True)
        self.abstract_tag = abstract_tag
        self.abstract_class = abstract_class
        self.toggle_depth = 0
        self.meta = {}
        self.abstract = []
        self.depth = 0
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript"} or (self.depth and tag in {"h1", "h2", "h3", "h4", "h5", "h6"}):
            self.hidden += 1
        if tag == "meta" and not self.hidden:
            key = (attrs.get("name") or attrs.get("property") or "").casefold()
            if key and attrs.get("content") is not None:
                self.meta.setdefault(key, []).append(_clean(attrs["content"]))
        if self.depth and tag == "a" and attrs.get("onclick"):
            self.toggle_depth += 1
        if tag == self.abstract_tag and self.abstract_class in (attrs.get("class") or "").split() and not self.depth:
            self.depth = 1
        elif self.depth and tag not in _VOID:
            self.depth += 1
        if self.depth and tag in {"br", "p", "div"}:
            self.abstract.append(" ")

    def handle_endtag(self, tag):
        if tag == "a" and self.toggle_depth:
            self.toggle_depth -= 1
        if tag in {"script", "style", "noscript", "h1", "h2", "h3", "h4", "h5", "h6"} and self.hidden:
            self.hidden -= 1
        if self.depth and tag not in _VOID:
            self.depth -= 1
        if self.depth and tag in {"p", "div"}:
            self.abstract.append(" ")

    def handle_data(self, value):
        if self.depth and not self.hidden and not self.toggle_depth:
            self.abstract.append(value)


def parse_source_page(raw_html, source_url, *, expected_title=None, expected_doi=None, expected_arxiv=None):
    source = _valid_url(source_url)
    if not isinstance(raw_html, str):
        raise ValueError("Expected HTML text")
    parser = _Page()
    parser.feed(raw_html)
    first = lambda key: next(iter(parser.meta.get(key, [])), "")
    title = first("citation_title")
    if not title:
        raise ValueError("No scholarly paper title")
    doi = _doi(first("citation_doi"))
    arxiv = first("citation_arxiv_id")
    if doi and not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
        raise ValueError("Invalid DOI metadata")
    if arxiv and not _ARXIV.fullmatch(arxiv):
        raise ValueError("Invalid arXiv metadata")
    if expected_doi is not None and _doi(expected_doi) != doi:
        raise ValueError("DOI mismatch")
    if expected_arxiv is not None and (not arxiv or _arxiv(expected_arxiv) != _arxiv(arxiv)):
        raise ValueError("arXiv mismatch")
    if expected_title:
        normalize = lambda value: re.sub(r"\W+", " ", value.casefold()).strip()
        if SequenceMatcher(None, normalize(expected_title), normalize(title)).ratio() < 0.93:
            raise ValueError("Title mismatch")
    # A matching identifier in an unrelated landing page must not be enough.
    if source.hostname in {"arxiv.org", "www.arxiv.org"}:
        path_id = source.path.removeprefix("/abs/").rstrip("/")
        if not source.path.startswith("/abs/") or not arxiv or _arxiv(path_id) != _arxiv(arxiv):
            raise ValueError("arXiv page identity mismatch")
    else:
        path_id = source.path.strip("/")
        if not doi or doi.rsplit("/", 1)[-1] != path_id.casefold():
            raise ValueError("Publisher page identity mismatch")
    pdf_url = None
    candidate = first("citation_pdf_url")
    if candidate:
        try:
            pdf = _valid_url(candidate)
            if pdf.hostname != source.hostname:
                raise ValueError("PDF host mismatch")
            if arxiv and source.hostname in {"arxiv.org", "www.arxiv.org"}:
                pdf_id = pdf.path.removeprefix("/pdf/").removesuffix(".pdf")
                if not pdf.path.startswith("/pdf/") or _arxiv(pdf_id) != _arxiv(arxiv):
                    raise ValueError("PDF identity mismatch")
                # Preserve the version requested by the landing metadata.
                requested_version = re.search(r"v\d+$", expected_arxiv or path_id, re.I)
                if requested_version and not pdf_id.casefold().endswith(requested_version.group().casefold()):
                    raise ValueError("PDF version mismatch")
            elif pdf.path != "/" + path_id + ".pdf":
                raise ValueError("PDF identity mismatch")
            pdf_url = candidate
        except ValueError:
            pass
    abstract = first("citation_abstract")
    if source.hostname == "aclanthology.org" and not abstract:
        abstract = _clean("".join(parser.abstract))
    return {"title": title, "abstract": abstract,
            "authors": list(dict.fromkeys(parser.meta.get("citation_author", []))),
            "date": _date(first("citation_date") or first("citation_publication_date")),
            "external_ids": {k: v for k, v in (("doi", doi), ("arxiv", arxiv)) if v},
            "pdf_url": pdf_url}


def parse_arxiv_search_abstract(raw_html):
    parser = _Page("span", "abstract-full")
    parser.feed(raw_html)
    return _clean("".join(parser.abstract))
