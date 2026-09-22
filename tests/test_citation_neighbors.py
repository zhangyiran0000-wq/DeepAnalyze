import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from deepanalyze.literature import LiteratureClient, LiteratureError, _paper

class CitationNeighborTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.cache = Path(directory.name)

    def test_both_directions_have_verified_provenance_and_offset(self):
        urls=[]
        def fetch(url):
            urls.append(url)
            if "/citations?" in url: return json.dumps({"data":[{"citingPaper":{"paperId":"c","title":"Citing","externalIds":{},"authors":[]}}]}).encode()
            return json.dumps({"data":[{"citedPaper":{"paperId":"r","title":"Reference","externalIds":{},"authors":[]}}]}).encode()
        client=LiteratureClient(self.cache,fetcher=fetch)
        anchor=_paper("Anchor",external_ids={"s2":"anchor"})
        rows=client.related(anchor,limit=3,offset=4)
        self.assertEqual({r["title"] for r in rows},{"Citing","Reference"})
        self.assertTrue(all(r["citation_links"][0]["anchor_id"]==anchor["id"] for r in rows))
        self.assertEqual({r["citation_links"][0]["direction"] for r in rows},{"cites_anchor","cited_by_anchor"})
        self.assertTrue(all(parse_qs(urlsplit(u).query)["offset"]==["4"] for u in urls))
        self.assertTrue(all(u.startswith("https://api.semanticscholar.org/graph/v1/paper/") for u in urls))

    def test_empty_citation_endpoint_does_not_title_search(self):
        client=LiteratureClient(self.cache,fetcher=lambda _: (_ for _ in ()).throw(LiteratureError('offline')))
        client.search=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError("no fallback search"))
        anchor=_paper("Anchor",external_ids={"s2":"anchor"})
        with self.assertRaises(LiteratureError): client.related(anchor,direction="citations")

    def test_legacy_public_scholar_url_recovers_exact_id_without_title_search(self):
        urls = []
        client = LiteratureClient(self.cache, fetcher=lambda url: urls.append(url) or b'{"data": []}')
        paper_id = "a" * 40
        client.related({"id": "saved", "title": "Saved title", "url": "https://www.semanticscholar.org/paper/title/" + paper_id}, direction="references")
        self.assertEqual(len(urls), 1)
        self.assertIn("/paper/" + paper_id + "/references?", urls[0])

    def test_offset_rejects_negative_bool_and_float(self):
        client=LiteratureClient(self.cache,fetcher=lambda _: (_ for _ in ()).throw(LiteratureError('offline')))
        anchor=_paper("Anchor",external_ids={"s2":"anchor"})
        for value in (-1, True, 1.5):
            with self.subTest(value=value):
                with self.assertRaises(LiteratureError): client.related(anchor, offset=value)

    def test_neighbor_page_is_bounded_and_reports_exact_count(self):
        urls = []
        def fetch(url):
            urls.append(url)
            if "/paper/anchor?" in url:
                return b'{"citationCount": 137, "referenceCount": 29}'
            return b'{"data":[{"citingPaper":{"paperId":"c","title":"Citing","externalIds":{},"authors":[]}}]}'
        client = LiteratureClient(self.cache, fetcher=fetch)
        anchor = _paper("Anchor", external_ids={"s2":"anchor"})
        page = client.neighbor_page(anchor, "citations", offset=40, limit=100, include_total=True)
        self.assertEqual(page["total"], 137)
        self.assertIsNone(page["next_offset"])
        self.assertEqual(page["papers"][0]["citation_links"][0]["direction"], "cites_anchor")
        self.assertIn("limit=100", urls[0])
        self.assertIn("offset=40", urls[0])

    def test_neighbor_page_metadata_only_uses_lightweight_fields_and_provider_next(self):
        urls = []
        def fetch(url):
            urls.append(url)
            return json.dumps({"next": 105, "data": [{"citingPaper": {"paperId": "c", "title": "Citing", "year": 2024, "externalIds": {}, "url": "https://example.org/c"}}]}).encode()
        client = LiteratureClient(self.cache, fetcher=fetch)
        anchor = _paper("Anchor", external_ids={"s2": "anchor"})
        page = client.neighbor_page(anchor, "citations", offset=5, limit=100, metadata_only=True)
        query = parse_qs(urlsplit(urls[0]).query)
        self.assertEqual(query["fields"], ["paperId,title,year,publicationDate,externalIds,url"])
        self.assertEqual(page["next_offset"], 105)
        self.assertEqual(page["papers"][0]["year"], 2024)
        self.assertEqual(page["papers"][0]["abstract"], "")

    def test_filtered_rows_do_not_truncate_raw_pagination(self):
        payload = {"data": [{"citingPaper": None}, {"citingPaper": {"title": "Visible record", "externalIds": {}}}]}
        client = LiteratureClient(self.cache, fetcher=lambda _: json.dumps(payload).encode())
        anchor = _paper("Anchor", external_ids={"s2": "anchor"})
        page = client.neighbor_page(anchor, "citations", offset=10, limit=2)
        self.assertEqual(len(page["papers"]), 1)
        self.assertEqual(page["next_offset"], 12)

    def test_explicit_end_and_invalid_pages_are_not_confused(self):
        anchor = _paper("Anchor", external_ids={"s2": "anchor"})
        payload = {"next": None, "data": [{"citingPaper": {"title": "Last record", "externalIds": {}}}]}
        client = LiteratureClient(self.cache, fetcher=lambda _: json.dumps(payload).encode())
        self.assertIsNone(client.neighbor_page(anchor, "citations", limit=1)["next_offset"])
        for payload in ({"data": None}, {"error": "temporarily unavailable"}, {"data": [], "next": 0}):
            client._json = lambda _, value=payload: value
            with self.assertRaises(LiteratureError): client.neighbor_page(anchor, "citations")

if __name__ == "__main__": unittest.main()
