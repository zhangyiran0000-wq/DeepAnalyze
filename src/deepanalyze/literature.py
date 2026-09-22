"""Bounded public scholarly retrieval with a reusable local evidence cache.

Only allowlisted public scholarly services are fetched. Publisher full text that
cannot be read is explicitly marked as abstract-only, never silently fabricated.
"""

from __future__ import annotations

import copy
import hashlib
import html
import io
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path

from .source_pages import parse_source_page, parse_arxiv_search_abstract


class LiteratureError(RuntimeError):
    """A public, credential-free retrieval failure with a safe category."""

    def __init__(self, message, *, code="source_unavailable"):
        super().__init__(message)
        self.code = code


HOSTS = {"api.semanticscholar.org", "api.crossref.org", "export.arxiv.org", "arxiv.org", "www.arxiv.org", "aclanthology.org"}
ARXIV = re.compile(r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?", re.I)
FIELDS = "paperId,title,abstract,year,publicationDate,url,authors,externalIds,citationCount"
METADATA_FIELDS = "paperId,title,year,publicationDate,externalIds,url"
READ_CACHE_VERSION = 3


def _allowed(url: str) -> bool:
    try:
        value = urllib.parse.urlsplit(url)
        return value.scheme == "https" and value.hostname in HOSTS and value.port in (None, 443) and not value.username and not value.password
    except ValueError:
        return False


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _allowed(newurl):
            raise LiteratureError("The source redirected outside supported scholarly hosts.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self.hidden += 1
        if not self.hidden and tag in ("p", "div", "section", "h1", "h2", "h3", "li", "tr", "br"):
            self.blocks.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header") and self.hidden:
            self.hidden -= 1
        if not self.hidden and tag in ("p", "div", "section", "h1", "h2", "h3", "li", "tr"):
            self.blocks.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.blocks.append(data)

    def text(self):
        return "\n".join(line.strip() for line in "".join(self.blocks).splitlines() if line.strip())


def _plain(value: str) -> str:
    parser = _Text()
    parser.feed(value or "")
    return parser.text()


def _norm(value: str) -> str:
    return re.sub(r"\W+", " ", value.casefold()).strip()


def _paper(title, *, date=None, url="", abstract="", authors=None, affiliations=None, external_ids=None, year=None, metadata_source="", metadata_label="Source metadata"):
    external_ids = external_ids or {}
    arxiv = external_ids.get("arxiv")
    doi = external_ids.get("doi")
    identity = "arxiv:" + re.sub(r"v\d+$", "", arxiv) if arxiv else ("doi:" + doi.casefold() if doi else "title:" + _norm(title))
    result = {
        "id": "p_" + hashlib.sha256(identity.encode()).hexdigest()[:16],
        "title": " ".join(title.split()), "short_name": " ".join(title.split())[:64],
        "year": int(date[:4]) if date and date[:4].isdigit() else year,
        "date": date, "url": url, "abstract": _plain(abstract),
        "authors": authors or [], "affiliations": affiliations or [],
        "metadata_source": metadata_source or url, "metadata_label": metadata_label,
        "external_ids": external_ids, "source_status": "abstract_only" if abstract else "metadata_only",
        "passages": [], "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
    if result["abstract"]:
        result["passages"] = [{"id": result["id"] + ":abstract", "text": result["abstract"], "location": "Abstract", "url": url}]
    return _normalize_record(result)


def _normalize_record(record):
    """Retain literal institution names and metadata provenance as evidence.

    Snippets are exact metadata field values, not invented sentences or a claim
    that the publication itself was inspected. Legacy caches keep their actual
    extraction status when their schema is migrated.
    """
    result = copy.deepcopy(record)
    result.setdefault("stable_original_id", result.get("id"))
    result.setdefault("alias_external_ids", {})
    status = result.get("source_status")
    result["source_status"] = {"abstract": "abstract_only", "metadata": "metadata_only"}.get(status, status) or ("abstract_only" if result.get("abstract") else "metadata_only")
    passages = [item for item in result.get("passages", []) if isinstance(item, dict) and item.get("kind") != "metadata_affiliation"]
    if result.get("abstract") and not any("abstract" in p.get("location", "").lower() for p in passages):
        passages.insert(0, {"id": result["id"] + ":abstract", "text": result["abstract"],
                           "location": "Abstract", "url": result.get("url", "")})
    affiliations, seen = [], set()
    for index, raw in enumerate(result.get("affiliations", [])):
        if isinstance(raw, str):
            raw = {"name": raw, "quote": raw}
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
            continue
        name = " ".join(_plain(raw["name"]).split())
        quote = raw.get("quote") if isinstance(raw.get("quote"), str) else raw["name"]
        source_url = raw.get("source_url") or result.get("metadata_source") or result.get("url", "")
        key = (name, source_url)
        if not name or not quote.strip() or key in seen:
            continue
        seen.add(key)
        label = result.get("metadata_label") or "Cached source metadata"
        location = raw.get("location") or f"{label}: affiliation name {index + 1}"
        item = {"name": name, "url": raw.get("url", ""), "quote": quote,
                "source_url": source_url, "source_kind": "metadata", "location": location}
        affiliations.append(item)
        digest = hashlib.sha256((source_url + quote).encode()).hexdigest()[:12]
        passages.append({"id": result["id"] + ":affiliation:" + digest, "text": quote,
                         "location": location, "url": source_url, "kind": "metadata_affiliation"})
    result["affiliations"] = affiliations
    result["passages"] = passages
    return result



class LiteratureClient:
    def __init__(self, cache_dir: Path, *, timeout: float = 15, fetcher=None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.fetcher = fetcher
        self._lock = threading.RLock()
        self._last_request: dict[str, float] = {}
        self._read_index = None
        self._opener = urllib.request.build_opener(_Redirect())

    def _fetch(self, url, *, max_bytes=5_000_000, ttl=21600):
        if not _allowed(url):
            raise LiteratureError("Only supported public scholarly URLs can be retrieved.")
        key = hashlib.sha256(url.encode()).hexdigest()
        target = self.cache_dir / (key + ".bin")
        with self._lock:
            if target.exists() and time.time() - target.stat().st_mtime < ttl:
                return target.read_bytes()
            if self.fetcher:
                body = self.fetcher(url)
            else:
                host = urllib.parse.urlsplit(url).hostname
                interval = 3.1 if host == "export.arxiv.org" else 1.05
                wait = interval - (time.monotonic() - self._last_request.get(host, 0))
                if wait > 0:
                    time.sleep(wait)
                self._last_request[host] = time.monotonic()
                request = urllib.request.Request(url, headers={"User-Agent": "DeepAnalyze/0.1 (local scholarly research client)", "Accept": "application/json, application/atom+xml, text/html, application/pdf;q=0.8"})
                try:
                    with self._opener.open(request, timeout=self.timeout) as response:
                        if not _allowed(response.url):
                            raise LiteratureError("Unsupported source redirect.")
                        body = response.read(max_bytes + 1)
                except urllib.error.HTTPError as exc:
                    raise LiteratureError(f"Scholarly source returned HTTP {exc.code}; try again later or use an exact identifier.") from None
                except (urllib.error.URLError, TimeoutError, OSError):
                    raise LiteratureError("Scholarly source is temporarily unreachable.") from None
            if len(body) > max_bytes:
                raise LiteratureError("Source exceeds the configured download size limit.")
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(body)
            tmp.replace(target)
            return body

    def _json(self, url):
        try:
            return json.loads(self._fetch(url))
        except (ValueError, UnicodeError):
            raise LiteratureError("Scholarly source returned invalid metadata.") from None

    def _s2_paper(self, item):
        ext = item.get("externalIds") or {}
        arxiv = ext.get("ArXiv")
        doi = ext.get("DOI")
        url = f"https://arxiv.org/abs/{arxiv}" if arxiv else (f"https://doi.org/{doi}" if doi else item.get("url", ""))
        result = _paper(item.get("title", "Untitled"), date=item.get("publicationDate"), year=item.get("year"), url=url, abstract=item.get("abstract") or "", authors=[a.get("name", "") for a in item.get("authors", [])], external_ids={k: v for k, v in {"arxiv": arxiv, "doi": doi, "s2": item.get("paperId")}.items() if v})
        result["author_ids"] = list(dict.fromkeys("s2:" + str(a["authorId"]) for a in item.get("authors", [])
                                                  if isinstance(a, dict) and a.get("authorId")))
        result["citation_count"] = item.get("citationCount")
        return result

    def _merge_enrichment(self, original, enriched, *, source_label):
        merged = copy.deepcopy(original)
        original_id = original.get("stable_original_id") or original.get("id")
        merged["stable_original_id"] = original_id
        aliases = dict(original.get("alias_external_ids") or {})
        for key, value in (enriched.get("external_ids") or {}).items():
            if value and value != (original.get("external_ids") or {}).get(key): aliases.setdefault(key, value)
        merged["alias_external_ids"] = aliases
        ids = dict(original.get("external_ids") or {}); ids.update({k:v for k,v in (enriched.get("external_ids") or {}).items() if v}); merged["external_ids"] = ids
        for field in ("abstract", "year", "date", "authors", "author_ids", "affiliations", "citation_count"):
            if not merged.get(field) and enriched.get(field): merged[field] = copy.deepcopy(enriched[field])
        if enriched.get("abstract") and not any(x.get("location") == "Abstract" for x in merged.get("passages", []) if isinstance(x, dict)):
            merged.setdefault("passages", []).insert(0, {"id": original_id + ":abstract", "text": enriched["abstract"], "location": "Abstract", "url": enriched.get("url", "")})
        arxiv = (enriched.get("external_ids") or {}).get("arxiv")
        if arxiv:
            arxiv = re.sub(r"v\d+$", "", arxiv); merged["available_arxiv_html"] = "https://arxiv.org/html/" + arxiv; merged["available_arxiv_pdf"] = "https://arxiv.org/pdf/" + arxiv
        if enriched.get("available_source_pdf"):
            merged["available_source_pdf"] = enriched["available_source_pdf"]
        merged["enrichment_source"] = source_label
        return _normalize_record(merged)

    def _landing_paper(self, url, *, expected_title=None, expected_doi=None, expected_arxiv=None):
        raw = self._fetch(url, max_bytes=3_000_000).decode("utf-8", "replace")
        try:
            data = parse_source_page(raw, url, expected_title=expected_title,
                                     expected_doi=expected_doi, expected_arxiv=expected_arxiv)
        except ValueError:
            raise LiteratureError("The source page did not match the expected paper identity.") from None
        paper = _paper(data["title"], date=data.get("date"), url=url,
                       abstract=data.get("abstract", ""), authors=data.get("authors", []),
                       external_ids=data.get("external_ids", {}), metadata_source=url,
                       metadata_label="Official scholarly landing page")
        if data.get("pdf_url"):
            paper["available_source_pdf"] = data["pdf_url"]
        return paper

    def _enrich_alternate_sources(self, paper):
        title = paper.get("title", ""); doi = (paper.get("external_ids") or {}).get("doi")
        # ACL DOI suffixes provide an exact publisher landing page without
        # broad web crawling or interpreting arbitrary links from a document.
        acl = re.fullmatch(r"10\.(?:18653|3115)/v1/([A-Za-z0-9.-]+)", doi or "", re.I)
        if acl:
            try:
                alt = self._landing_paper("https://aclanthology.org/" + acl.group(1) + "/",
                                          expected_title=title, expected_doi=doi)
                paper = self._merge_enrichment(paper, alt, source_label="ACL Anthology landing page")
            except LiteratureError:
                pass
        if doi:
            try:
                url = "https://api.semanticscholar.org/graph/v1/paper/DOI:" + urllib.parse.quote(doi, safe="") + "?" + urllib.parse.urlencode({"fields": FIELDS})
                alt = self._s2_paper(self._json(url)); exact = (alt.get("external_ids") or {}).get("doi", "").casefold() == doi.casefold(); strong = SequenceMatcher(None, _norm(title), _norm(alt.get("title", ""))).ratio() >= 0.88
                if exact and strong:
                    paper = self._merge_enrichment(paper, alt, source_label="Semantic Scholar DOI metadata")
                    if paper.get("abstract"): return paper
            except LiteratureError: pass
        try:
            candidates = self._arxiv(query=title, limit=5, exact_title=True); ranked = sorted(((SequenceMatcher(None, _norm(title), _norm(x.get("title", ""))).ratio(), x) for x in candidates), key=lambda pair: pair[0], reverse=True)
            if ranked and ranked[0][0] >= 0.93: paper = self._merge_enrichment(paper, ranked[0][1], source_label="arXiv title metadata")
        except LiteratureError: pass
        return paper

    def _arxiv(self, *, identifier=None, query=None, limit=10, year_from=None, year_to=None, sort="relevance", exact_title=False):
        if identifier:
            args = {"id_list": identifier}
        else:
            raw_query = str(query or "").replace(chr(34), "").strip()
            if exact_title:
                search_query = "ti:\"" + raw_query + "\""
            else:
                tokens = [token for x in raw_query.split() if len(x) > 2 for token in [re.sub(r"[^A-Za-z0-9]", "", x)] if token]
                search_query = "all:(" + " AND ".join(tokens[:10]) + ")"
            if year_from or year_to:
                lower = str(year_from or 1).zfill(4) + "01010000"
                upper = str(year_to or datetime.now(timezone.utc).year).zfill(4) + "12312359"
                search_query += " AND submittedDate:[" + lower + " TO " + upper + "]"
            args = {"search_query": search_query, "start": 0, "max_results": min(30, limit), "sortBy": "submittedDate" if sort == "newest" else "relevance", "sortOrder": "descending"}

        metadata_url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(args)
        try:
            raw = self._fetch(metadata_url)
            root = ET.fromstring(raw)
        except (LiteratureError, ET.ParseError):
            root = None
        ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
        results = []
        for entry in (root.findall("a:entry", ns) if root is not None else []):
            identity = entry.findtext("a:id", "", ns)
            match = ARXIV.search(identity)
            if not match:
                continue
            aid = match.group(0)
            affiliations = [x.text or "" for x in entry.findall("a:author/x:affiliation", ns)]
            results.append(_paper(entry.findtext("a:title", "", ns), date=entry.findtext("a:published", "", ns)[:10] or None, url=f"https://arxiv.org/abs/{aid}", abstract=entry.findtext("a:summary", "", ns), authors=[a.findtext("a:name", "", ns) for a in entry.findall("a:author", ns)], affiliations=affiliations, external_ids={"arxiv": aid}, metadata_source=metadata_url, metadata_label="arXiv Atom metadata"))
        if not results and identifier:
            try:
                results = [self._landing_paper("https://arxiv.org/abs/" + identifier,
                                              expected_arxiv=identifier)]
            except LiteratureError:
                pass
        if not results and query and not identifier:
            page_args = {"query": str(query)[:300], "searchtype": "title" if exact_title else "all", "abstracts": "show"}
            if sort == "newest":
                page_args["order"] = "-announced_date_first"
            page_url = "https://arxiv.org/search/?" + urllib.parse.urlencode(page_args)
            try:
                page = self._fetch(page_url, max_bytes=3_000_000).decode("utf-8", "replace")
                for block in re.findall(r"<li[^>]+class=\"arxiv-result\".*?</li>", page, re.S | re.I)[:limit]:
                    link = re.search(r"href=\"https?://arxiv.org/abs/([^\"]+)", block)
                    heading = re.search(r"<p[^>]+class=\"title[^>]*>(.*?)</p>", block, re.S | re.I)
                    abstract = parse_arxiv_search_abstract(block)
                    if link and heading:
                        aid = re.sub(r"v\d+$", "", link.group(1))
                        submitted = re.search(r"Submitted.*?(\d{1,2}\s+[A-Za-z]+,?\s+\d{4}|\d{4}-\d{2}-\d{2})", block, re.S | re.I)
                        date = None
                        if submitted:
                            raw_date = re.sub(r"\s+", " ", submitted.group(1)).replace(",", "")
                            for fmt in ("%d %B %Y", "%Y-%m-%d"):
                                try: date = datetime.strptime(raw_date, fmt).date().isoformat(); break
                                except ValueError: pass
                        authors = re.findall(r"<a[^>]+href=\"/search/\?searchtype=author[^>]*>(.*?)</a>", block, re.S | re.I)
                        results.append(_paper(_plain(heading.group(1)), date=date, authors=[_plain(x) for x in authors], url="https://arxiv.org/abs/" + aid, abstract=abstract, external_ids={"arxiv": aid}, metadata_source=page_url, metadata_label="arXiv search metadata"))
            except LiteratureError:
                pass
        return results

    def _crossref_paper(self, item):
        titles = item.get("title") or []
        title = titles[0] if titles else "Untitled"
        parts = (item.get("published") or item.get("issued") or {}).get("date-parts", [[]])[0]
        date = "-".join(str(x).zfill(2 if i else 4) for i, x in enumerate(parts)) if parts else None
        authors = [" ".join(filter(None, [a.get("given"), a.get("family")])) for a in item.get("author", [])]
        affiliations = [f.get("name", "") for a in item.get("author", []) for f in a.get("affiliation", []) if f.get("name")]
        doi = item.get("DOI", "")
        return _paper(title, date=date, url="https://doi.org/" + doi, abstract=item.get("abstract", ""), authors=authors, affiliations=affiliations, external_ids={"doi": doi}, metadata_source="https://api.crossref.org/works/" + urllib.parse.quote(doi, safe=""), metadata_label="Crossref author affiliation metadata")

    def resolve(self, seed):
        seed = str(seed).strip()
        if not seed or len(seed) > 1000:
            raise LiteratureError("Enter a paper title, DOI, or arXiv identifier.")
        aid = None
        if seed.lower().startswith(("https://arxiv.org/", "http://arxiv.org/", "arxiv:")) or ARXIV.fullmatch(seed):
            match = ARXIV.search(seed)
            aid = match.group(0) if match else None
        if aid:
            try:
                results = self._arxiv(identifier=aid)
                if results:
                    return results[0]
            except LiteratureError:
                pass
            data = self._json("https://api.semanticscholar.org/graph/v1/paper/" + urllib.parse.quote("ARXIV:" + re.sub(r"v\d+$", "", aid), safe="") + "?" + urllib.parse.urlencode({"fields": FIELDS}))
            return self._s2_paper(data)
        doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", seed, flags=re.I)
        if re.match(r"^10\.\d{4,9}/\S+$", doi):
            data = self._json("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe=""))
            return self._enrich_alternate_sources(self._crossref_paper(data["message"]))
        acl_url = re.fullmatch(r"https://aclanthology\.org/([A-Za-z0-9.-]+)/?", seed, re.I)
        if acl_url:
            return self._landing_paper("https://aclanthology.org/" + acl_url.group(1) + "/")
        if "://" in seed:
            raise LiteratureError("Use a paper title, DOI link, arXiv link, or ACL Anthology paper link. Arbitrary URLs are not fetched.")
        search_error = None
        try:
            results = self.search(seed, limit=5)
        except LiteratureError as error:
            results, search_error = [], error
        def rank(candidates):
            return sorted(((SequenceMatcher(None, _norm(seed), _norm(p["title"])).ratio(), p)
                           for p in candidates), key=lambda pair: pair[0], reverse=True)
        scored = rank(results)
        # A nonempty topical result list is not a resolved paper identity. Web
        # fallbacks can favor recent related works, so try a bounded title-only
        # query before declaring an older seed ambiguous or unavailable.
        if not scored or scored[0][0] < 0.93:
            try:
                precise = self._arxiv(query=seed, limit=5, exact_title=True)
                scored = rank(results + precise)
            except LiteratureError:
                pass
        if not scored:
            if search_error:
                raise search_error
            raise LiteratureError("No matching paper was found. Try the DOI or arXiv identifier.", code="source_not_found")
        if scored[0][0] < 0.56 or (len(scored) > 1 and scored[0][0] < 0.9 and scored[0][0] - scored[1][0] < 0.07):
            raise LiteratureError("The title is ambiguous. Use the full title, DOI, or arXiv identifier.", code="ambiguous_title")
        paper = scored[0][1]
        paper["resolution_similarity"] = round(scored[0][0], 3)
        return paper

    def search(self, query, limit=10, *, year_from=None, year_to=None, sort="relevance"):
        query = str(query).strip()[:500]
        limit = max(1, min(30, int(limit)))
        year_from = int(year_from) if year_from is not None else None
        year_to = int(year_to) if year_to is not None else None
        if year_from is not None and year_to is not None and year_to < year_from:
            raise LiteratureError("year_to must be greater than or equal to year_from")
        if not query:
            return []
        if sort not in {"relevance", "newest"}:
            raise LiteratureError("sort must be relevance or newest")
        errors = []
        try:
            params = {"query": query, "limit": min(30, limit * 2 if sort == "newest" else limit), "fields": FIELDS}
            if year_from is not None or year_to is not None:
                params["year"] = str(year_from or 1) + "-" + str(year_to or "")
            data = self._json("https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params))
            results = [self._s2_paper(x) for x in data.get("data", []) if x.get("title")]
            if year_from is not None: results = [x for x in results if x.get("year") and x["year"] >= year_from]
            if year_to is not None: results = [x for x in results if x.get("year") and x["year"] <= year_to]
            if sort == "newest": results.sort(key=lambda x: x.get("year") or 0, reverse=True)
            if results: return results[:limit]
        except LiteratureError as exc:
            errors.append(str(exc))
        try:
            results = self._arxiv(query=query, limit=limit * 2 if sort == "newest" else limit, year_from=year_from, year_to=year_to, sort=sort)
            if year_from is not None: results = [x for x in results if x.get("year") and x["year"] >= year_from]
            if year_to is not None: results = [x for x in results if x.get("year") and x["year"] <= year_to]
            if sort == "newest": results.sort(key=lambda x: x.get("year") or 0, reverse=True)
            if results: return results[:limit]
        except LiteratureError as exc:
            errors.append(str(exc))
        try:
            params = {"query.title": query, "rows": limit * 2 if sort == "newest" else limit}
            filters = []
            if year_from is not None: filters.append("from-pub-date:" + str(year_from) + "-01-01")
            if year_to is not None: filters.append("until-pub-date:" + str(year_to) + "-12-31")
            if filters: params["filter"] = ",".join(filters)
            if sort == "newest": params.update(sort="published", order="desc")
            data = self._json("https://api.crossref.org/works?" + urllib.parse.urlencode(params))
            results = [self._crossref_paper(x) for x in data.get("message", {}).get("items", []) if x.get("title")]
            if year_from is not None: results = [x for x in results if x.get("year") and x["year"] >= year_from]
            if year_to is not None: results = [x for x in results if x.get("year") and x["year"] <= year_to]
            if sort == "newest": results.sort(key=lambda x: x.get("year") or 0, reverse=True)
            return results[:limit]
        except LiteratureError:
            raise LiteratureError("Literature search providers are unavailable or rate-limited; retry later.") from None

    @staticmethod
    def _citation_identity(paper):
        ext = paper.get("external_ids") or {}
        identity = ext.get("s2") or ("ARXIV:" + re.sub(r"v\d+$", "", ext["arxiv"]) if ext.get("arxiv") else ("DOI:" + ext["doi"] if ext.get("doi") else None))
        if identity:
            return identity
        # Resumed legacy snapshots may predate external_ids. Recover only
        # identities encoded by supported canonical URLs; never infer from a
        # title or arbitrary publisher URL.
        for field in ("url", "available_arxiv_html", "available_arxiv_pdf"):
            raw_url = paper.get(field)
            if not isinstance(raw_url, str):
                continue
            try:
                parsed = urllib.parse.urlsplit(raw_url)
            except ValueError:
                continue
            host = (parsed.hostname or "").casefold()
            if host in {"arxiv.org", "www.arxiv.org"} and parsed.path.startswith(("/abs/", "/pdf/")):
                match = ARXIV.search(parsed.path)
                if match:
                    return "ARXIV:" + re.sub(r"v\d+$", "", match.group(0))
            if host in {"semanticscholar.org", "www.semanticscholar.org"}:
                match = re.fullmatch(r"/paper/(?:[^/]+/)?([a-fA-F0-9]{40})/?", parsed.path)
                if match:
                    return match.group(1)
            if host == "api.semanticscholar.org":
                match = re.fullmatch(r"/graph/v1/paper/([^/]+)", parsed.path.rstrip("/"))
                if match and match.group(1):
                    return urllib.parse.unquote(match.group(1))
            if host in {"doi.org", "dx.doi.org"} and parsed.path.startswith("/"):
                doi = urllib.parse.unquote(parsed.path[1:]).strip()
                if re.fullmatch(r"10\.\d{4,9}/\S+", doi, re.I):
                    return "DOI:" + doi
        return None

    def neighbor_count(self, paper, direction):
        """Return the provider count for one exact citation relation."""
        if direction not in {"citations", "references"}:
            raise LiteratureError("direction must be citations or references")
        identity = self._citation_identity(paper)
        if not identity:
            raise LiteratureError("Citation lookup requires a verified paper identity.")
        url = "https://api.semanticscholar.org/graph/v1/paper/" + urllib.parse.quote(identity, safe="") + "?" + urllib.parse.urlencode({"fields": "citationCount,referenceCount"})
        data = self._json(url)
        key = "citationCount" if direction == "citations" else "referenceCount"
        value = data.get(key)
        return value if type(value) is int and value >= 0 else None

    def neighbor_page(self, paper, direction, *, offset=0, limit=100, include_total=False, metadata_only=False):
        """Fetch one bounded, directly cited/citing page with provenance."""
        if direction not in {"citations", "references"}:
            raise LiteratureError("direction must be citations or references")
        if isinstance(offset, bool) or type(offset) is not int or offset < 0:
            raise LiteratureError("offset must be a non-negative integer")
        if isinstance(limit, bool) or type(limit) is not int or limit <= 0:
            raise LiteratureError("limit must be a positive integer")
        if not isinstance(metadata_only, bool):
            raise LiteratureError("metadata_only must be boolean")
        limit = min(1000, limit)
        identity = self._citation_identity(paper)
        if not identity:
            raise LiteratureError("Citation lookup requires a verified paper identity.")
        key = "citingPaper" if direction == "citations" else "citedPaper"
        fields = METADATA_FIELDS if metadata_only else FIELDS
        url = "https://api.semanticscholar.org/graph/v1/paper/" + urllib.parse.quote(identity, safe="") + "/" + direction + "?" + urllib.parse.urlencode({"fields": fields, "limit": limit, "offset": offset})
        payload = self._json(url)
        raw_rows = payload.get("data")
        if not isinstance(raw_rows, list):
            raise LiteratureError("Citation provider returned an invalid page.")
        rows = []
        for item in raw_rows:
            record = item.get(key) if isinstance(item, dict) else None
            if not isinstance(record, dict): continue
            if not record.get("title"):
                continue
            result = self._s2_paper(record)
            result["discovery_relation"] = direction
            result["discovery_source"] = paper.get("id") or identity
            result["citation_links"] = [{"anchor_id": paper.get("id") or identity,
                                          "direction": "cites_anchor" if direction == "citations" else "cited_by_anchor",
                                          "source_url": url}]
            rows.append(result)
        provider_next = payload.get("next")
        if "next" in payload:
            if provider_next is not None and (type(provider_next) is not int or provider_next <= offset):
                raise LiteratureError("Citation provider returned an invalid continuation.")
            next_offset = provider_next
        else:
            # The cursor counts raw relation rows, including malformed records
            # that cannot become candidates. Filtering must not skip later pages.
            next_offset = offset + len(raw_rows) if len(raw_rows) == limit else None
        page = {"papers": rows, "offset": offset,
                "next_offset": next_offset, "total": None}
        if include_total:
            page["total"] = self.neighbor_count(paper, direction)
        return page

    def related(self, paper, limit=10, *, direction="both", offset=0):
        if direction not in {"both", "citations", "references"}:
            raise LiteratureError("direction must be citations, references, or both")
        if isinstance(offset, bool) or type(offset) is not int or offset < 0:
            raise LiteratureError("offset must be a non-negative integer")
        relations = ("citations", "references") if direction == "both" else (direction,)
        results = []
        failures = 0
        page_limit = max(1, min(30, limit))
        for relation in relations:
            try:
                results.extend(self.neighbor_page(paper, relation, offset=offset, limit=page_limit)["papers"])
            except LiteratureError:
                failures += 1
        if failures == len(relations):
            raise LiteratureError("Citation provider unavailable; retry later.")
        if not results:
            return []
        citations = [p for p in results if p["discovery_relation"] == "citations"]
        refs = [p for p in results if p["discovery_relation"] == "references"]
        merged = []
        for i in range(max(len(citations), len(refs))):
            merged.extend(x[i] for x in (citations, refs) if i < len(x))
        unique = {}
        for item in merged:
            prior = unique.get(item["id"])
            if prior:
                links = prior.setdefault("citation_links", []) + item.get("citation_links", [])
                prior["citation_links"] = list({(x.get("anchor_id"), x.get("direction"), x.get("source_url")): x for x in links}.values())
            else:
                unique[item["id"]] = item
        return list(unique.values())[:limit]

    @staticmethod
    def _read_keys(paper):
        if not isinstance(paper, dict): return set()
        keys = {"id:" + str(paper[key]) for key in ("id", "stable_original_id") if paper.get(key)}
        for key, value in (paper.get("external_ids") or {}).items():
            if key in {"doi", "arxiv", "s2"} and isinstance(value, str) and value:
                value = re.sub(r"v\d+$", "", value) if key == "arxiv" else value
                keys.add(key + ":" + value.casefold())
        return keys

    @staticmethod
    def _readable(paper):
        return any(len(p.get("text", "").strip()) >= 40 and p.get("kind") != "metadata_affiliation"
                   and "metadata" not in p.get("location", "").lower()
                   for p in paper.get("passages", []))

    def _read_target(self, paper):
        # An alias discovered later must not split the evidence cache in two.
        digest = hashlib.sha256(str(paper["id"]).encode()).hexdigest()
        return self.cache_dir / ("read_" + digest + ".json")

    def _cached_read(self, paper):
        def load(path):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(record, dict): return None
                cached = _normalize_record(record)
                if not self._read_keys(paper) & self._read_keys(cached):
                    return None
                # Never match on title alone, or silently accept conflicting IDs.
                current_ids, cached_ids = paper.get("external_ids") or {}, cached.get("external_ids") or {}
                for key in ("doi", "arxiv", "s2"):
                    if current_ids.get(key) and cached_ids.get(key):
                        a, b = str(current_ids[key]).casefold(), str(cached_ids[key]).casefold()
                        if key == "arxiv": a, b = re.sub(r"v\d+$", "", a), re.sub(r"v\d+$", "", b)
                        if a != b: return None
                if not self._readable(cached):
                    return None
                age = time.time() - path.stat().st_mtime
                if cached.get("source_status") != "fulltext" and age >= 3600:
                    return None
                return cached
            except (OSError, ValueError, TypeError):
                return None

        target = self._read_target(paper)
        direct = load(target)
        if direct and direct.get("source_status") == "fulltext":
            return direct, target
        # Legacy caches used id + optional arXiv ID. Build the identity index once
        # per client, then retain only path references rather than whole papers.
        with self._lock:
            if self._read_index is None:
                self._read_index = {}
                for path in self.cache_dir.glob("read_*.json"):
                    try:
                        record = json.loads(path.read_text(encoding="utf-8"))
                        for key in self._read_keys(record):
                            self._read_index.setdefault(key, set()).add(path)
                    except (OSError, ValueError, TypeError):
                        continue
            paths = {path for key in self._read_keys(paper) for path in self._read_index.get(key, set())}
        best = (direct, target) if direct else (None, None)
        for path in sorted(paths):
            cached = load(path)
            if cached and (best[0] is None or cached.get("source_status") == "fulltext"):
                best = cached, path
                if cached.get("source_status") == "fulltext": break
        return best

    def _reuse_read(self, cached, paper):
        result = copy.deepcopy(cached)
        old_id = result.get("id")
        result["id"] = result["stable_original_id"] = paper["id"]
        if old_id != paper["id"]:
            for passage in result.get("passages", []):
                passage["id"] = paper["id"] + ":" + hashlib.sha256(str(passage.get("id", "")).encode()).hexdigest()[:12]
        for field in ("title", "short_name", "authors", "author_ids", "affiliations", "metadata_source", "metadata_label", "url"):
            if paper.get(field): result[field] = copy.deepcopy(paper[field])
        for field in ("date", "year", "abstract"):
            if not result.get(field) and paper.get(field): result[field] = copy.deepcopy(paper[field])
        # A nested search-highlight span used to truncate abstracts. Safely
        # extend that cached prefix when the same paper supplies its full text.
        incoming, existing = paper.get("abstract") or "", result.get("abstract") or ""
        if existing and len(incoming) > len(existing) and incoming.startswith(existing):
            result["abstract"] = incoming
            for passage in result.get("passages", []):
                if passage.get("location") == "Abstract" and passage.get("text") == existing:
                    passage["text"] = incoming
                    passage["url"] = paper.get("url") or passage.get("url", "")
        result["external_ids"] = {**result.get("external_ids", {}), **paper.get("external_ids", {})}
        result = _normalize_record(result)
        result["cache_hit"] = True
        result["read_cache_version"] = READ_CACHE_VERSION
        if result.get("source_status") == "fulltext": result.pop("read_note", None)
        return result

    def read(self, paper):
        result = _normalize_record(paper)
        target = self._read_target(result)
        cached, cached_path = self._cached_read(result)
        if cached:
            result = self._reuse_read(cached, result)
            previous_mtime = cached_path.stat().st_mtime
            self._save_read(target, result)
            # Cache reads/migrations must not indefinitely extend abstract TTL.
            os.utime(target, (previous_mtime, previous_mtime))
            return result
        # Validation and resumed runs may pass a cached Crossref record directly,
        # bypassing resolve(); recover alternate identifiers before reading.
        if result.get("source_status") in {"metadata_only", "abstract_only"} and not (result.get("external_ids") or {}).get("arxiv"):
            result = self._enrich_alternate_sources(result)
        identifier = (result.get("external_ids") or {}).get("arxiv")
        if not identifier:
            match = ARXIV.search(paper.get("url", "")) if "arxiv.org/" in paper.get("url", "") else None
            identifier = match.group(0) if match else None
        if identifier and ARXIV.fullmatch(identifier) and not self._readable(result):
            try:
                alt = self._landing_paper("https://arxiv.org/abs/" + identifier,
                                          expected_title=result.get("title"), expected_arxiv=identifier)
                result = self._merge_enrichment(result, alt, source_label="arXiv landing page")
            except LiteratureError:
                pass
        # Enrichment may reveal an exact alias under which readable evidence was
        # already cached. Recheck before downloading the body.
        cached, cached_path = self._cached_read(result)
        if cached:
            result = self._reuse_read(cached, result)
            previous_mtime = cached_path.stat().st_mtime
            self._save_read(target, result)
            os.utime(target, (previous_mtime, previous_mtime))
            return result
        paragraphs = []
        source_url = paper.get("url", "")
        if identifier and ARXIV.fullmatch(identifier):
            source_url = "https://arxiv.org/html/" + identifier
            try:
                raw_html = self._fetch(source_url)
                html_affiliations = self._arxiv_html_affiliations(raw_html, source_url)
                if html_affiliations:
                    result["affiliations"] = result.get("affiliations", []) + html_affiliations
                    result = _normalize_record(result)
                text = _plain(raw_html.decode("utf-8", "replace"))
                if len(text) > 3000 and ("references" in text.casefold() or "introduction" in text.casefold()):
                    paragraphs = [("HTML paragraph " + str(i + 1), block) for i, block in enumerate(text.splitlines()) if len(block.strip()) > 40]
            except LiteratureError:
                pass
            if not paragraphs:
                try:
                    from pypdf import PdfReader
                    source_url = "https://arxiv.org/pdf/" + identifier
                    raw = self._fetch(source_url, max_bytes=20_000_000)
                    reader = PdfReader(io.BytesIO(raw))
                    for number, page in enumerate(reader.pages[:150], 1):
                        text = page.extract_text() or ""
                        if text.strip():
                            paragraphs.append((f"PDF page {number}", text))
                except (ImportError, LiteratureError):
                    result["read_note"] = "Full text unavailable; only supplied metadata/abstract can support claims. Install the optional PDF extra to enable PDF extraction."
                except Exception:
                    result["read_note"] = "Full text extraction failed; only supplied metadata/abstract can support claims."
        publisher_pdf = result.get("available_source_pdf")
        if not paragraphs and publisher_pdf and _allowed(publisher_pdf) and publisher_pdf != source_url:
            try:
                from pypdf import PdfReader
                raw = self._fetch(publisher_pdf, max_bytes=20_000_000)
                reader = PdfReader(io.BytesIO(raw))
                for number, page in enumerate(reader.pages[:150], 1):
                    text = page.extract_text() or ""
                    if text.strip():
                        paragraphs.append((f"PDF page {number}", text))
                if paragraphs:
                    source_url = publisher_pdf
            except (ImportError, LiteratureError):
                result["read_note"] = "Publisher PDF unavailable; only the recorded abstract can support claims."
            except Exception:
                result["read_note"] = "Publisher PDF extraction failed; only recorded source passages are available."
        if paragraphs:
            passages = []
            for location, block in paragraphs:
                for offset in range(0, len(block), 2400):
                    chunk = block[offset:offset + 2400].strip()
                    if chunk:
                        digest = hashlib.sha256((source_url + location + str(offset) + chunk).encode()).hexdigest()[:12]
                        passages.append({"id": paper["id"] + ":" + digest, "text": chunk, "location": location + (f", offset {offset}" if offset else ""), "url": source_url})
            metadata_passages = [item for item in result["passages"] if item.get("kind") == "metadata_affiliation"]
            result.update(source_status="fulltext", passages=passages + metadata_passages, fulltext_url=source_url)
            result.pop("read_note", None)
        else:
            result["source_status"] = "abstract_only" if result.get("abstract") else "metadata_only"
            result.setdefault("read_note", "No supported readable full text was available; use only the recorded evidence.")
        result = _normalize_record(result)
        result["cache_hit"] = False
        result["read_cache_version"] = READ_CACHE_VERSION
        self._save_read(target, result)
        return result

    @staticmethod
    def _arxiv_html_affiliations(raw, source_url):
        """Extract only explicit LaTeXML affiliation contact spans."""
        class AffiliationParser(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.level = 0
                self.sup_level = 0
                self.buffer = []
                self.values = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                classes = set((attrs.get("class") or "").split())
                if self.level == 0 and {"ltx_contact", "ltx_role_affiliation"}.issubset(classes):
                    self.level = 1
                    self.buffer = []
                    return
                if self.level:
                    self.level += 1
                    if tag == "sup":
                        self.sup_level += 1

            def handle_endtag(self, tag):
                if not self.level:
                    return
                if tag == "sup" and self.sup_level:
                    self.sup_level -= 1
                self.level -= 1
                if self.level == 0:
                    value = " ".join("".join(self.buffer).split())
                    value = re.sub(r"^Affiliation:\s*", "", value, flags=re.I).strip()
                    value = re.sub(r"\b(?:Equal contribution|Project lead)\b", "", value, flags=re.I)
                    value = " ".join(value.split())
                    if value and value not in self.values:
                        self.values.append(value)

            def handle_data(self, data):
                if self.level and not self.sup_level:
                    self.buffer.append(data)

        parser = AffiliationParser()
        try:
            parser.feed(raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw))
        except (ValueError, TypeError):
            return []
        return [{"name": value, "quote": value, "source_url": source_url,
                 "source_kind": "metadata", "location": "arXiv HTML author affiliation"}
                for value in parser.values]

    def _save_read(self, target, result):
        with self._lock:
            tmp = target.with_suffix(".tmp")
            tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            tmp.replace(target)
            if self._read_index is not None:
                for key in self._read_keys(result):
                    self._read_index.setdefault(key, set()).add(target)
