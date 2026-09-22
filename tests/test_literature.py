import json
import tempfile
import unittest
from pathlib import Path

from deepanalyze.literature import LiteratureClient, LiteratureError, _paper, _plain


class LiteratureTests(unittest.TestCase):
    def _temp_client(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return LiteratureClient(Path(tmp.name))
    def test_metadata_cache_avoids_repeat_network(self):
        calls = []
        def fetch(url):
            calls.append(url)
            return json.dumps({"data": [{"paperId": "one", "title": "A precise paper title", "year": 2020, "abstract": "Known evidence", "externalIds": {"ArXiv": "2001.12345"}, "authors": []}]}).encode()
        with tempfile.TemporaryDirectory() as tmp:
            client = LiteratureClient(Path(tmp), fetcher=fetch)
            first = client.resolve("A precise paper title")
            second = client.resolve("A precise paper title")
            self.assertEqual(first["id"], second["id"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(first["passages"][0]["text"], "Known evidence")

    def test_arbitrary_urls_are_not_fetched(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = LiteratureClient(Path(tmp), fetcher=lambda _: self.fail("must not fetch"))
            for seed in ("http://127.0.0.1/secret", "file:///private", "https://example.org/a.pdf"):
                with self.assertRaises(LiteratureError):
                    client.resolve(seed)
            with self.assertRaises(LiteratureError):
                client._fetch("https://api.crossref.org@127.0.0.1/private")

    def test_stable_arxiv_identity_across_versions(self):
        a = _paper("First title", external_ids={"arxiv": "2001.12345v1"})
        b = _paper("Revised title", external_ids={"arxiv": "2001.12345v2"})
        self.assertEqual(a["id"], b["id"])

    def test_unavailable_fulltext_is_not_reported_as_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = LiteratureClient(Path(tmp), fetcher=lambda _: b"")
            paper = _paper("Metadata only", url="https://doi.org/10.1234/test")
            result = client.read(paper)
            self.assertEqual(result["source_status"], "metadata_only")
            self.assertEqual(result["passages"], [])

    def test_crossref_affiliations_survive_read_cache_and_graph_validation(self):
        from deepanalyze.graph import build_snapshot
        metadata = {"message": {"DOI": "10.1234/synthetic", "title": ["Synthetic affiliation fixture"],
                    "published": {"date-parts": [[2020, 1, 2]]},
                    "abstract": "This synthetic source describes a bounded table operation.",
                    "author": [{"given": "Example", "family": "Author", "affiliation": [
                        {"name": "Fictional Analysis Institute"}, {"name": "Synthetic Systems Lab"}]}]}}
        with tempfile.TemporaryDirectory() as tmp:
            client = LiteratureClient(Path(tmp), fetcher=lambda url: json.dumps(metadata).encode())
            paper = client.resolve("10.1234/synthetic")
            source_url = "https://api.crossref.org/works/10.1234%2Fsynthetic"
            self.assertEqual(paper["source_status"], "abstract_only")
            self.assertEqual(paper["affiliations"][0]["quote"], "Fictional Analysis Institute")
            self.assertEqual(paper["affiliations"][0]["source_url"], source_url)
            self.assertEqual(paper["affiliations"][0]["source_kind"], "metadata")
            first = client.read(paper)
            # Simulate a legacy extraction cache with strings and the former status.
            cached_path = next(Path(tmp).glob("read_*.json"))
            legacy = json.loads(cached_path.read_text(encoding="utf-8"))
            legacy["source_status"] = "abstract"
            legacy["affiliations"] = [entry["name"] for entry in legacy["affiliations"]]
            legacy["passages"] = [entry for entry in legacy["passages"] if entry.get("kind") != "metadata_affiliation"]
            legacy.pop("metadata_source", None)
            legacy.pop("metadata_label", None)
            cached_path.write_text(json.dumps(legacy), encoding="utf-8")
            restored = client.read(paper)
            self.assertTrue(restored["cache_hit"])
            self.assertEqual(restored["source_status"], "abstract_only")
            self.assertEqual(restored["affiliations"], first["affiliations"])
            self.assertEqual(len([p for p in restored["passages"] if p.get("kind") == "metadata_affiliation"]), 2)
            snapshot = build_snapshot({"nodes": [{"id": paper["id"]}], "groups": [], "edges": [], "gaps": [], "review_notes": []},
                                      {paper["id"]: restored}, None, paper["id"], "Synthetic fixture", 1)
            institutions = snapshot["nodes"][0]["affiliations"]
            self.assertEqual([entry["name"] for entry in institutions], ["Fictional Analysis Institute", "Synthetic Systems Lab"])
            self.assertTrue(all(entry["source_url"] == source_url for entry in institutions))
            persisted = json.loads(cached_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["source_status"], "abstract_only")

    def test_fulltext_extraction_keeps_metadata_attribution(self):
        body = "<h1>Introduction</h1>" + "".join("<p>" + "Synthetic full-text evidence. " * 12 + "</p>" for _ in range(12))
        with tempfile.TemporaryDirectory() as tmp:
            client = LiteratureClient(Path(tmp), fetcher=lambda url: body.encode())
            paper = _paper("Synthetic extraction fixture", url="https://arxiv.org/abs/2001.12345",
                           affiliations=["Fictional Source Lab"], external_ids={"arxiv": "2001.12345"},
                           metadata_source="https://export.arxiv.org/api/query?id_list=2001.12345",
                           metadata_label="arXiv Atom metadata")
            result = client.read(paper)
            self.assertEqual(result["source_status"], "fulltext")
            metadata = [entry for entry in result["passages"] if entry.get("kind") == "metadata_affiliation"]
            self.assertEqual(len(metadata), 1)
            self.assertEqual(metadata[0]["text"], "Fictional Source Lab")
            self.assertTrue(any("HTML paragraph" in entry["location"] for entry in result["passages"]))
            self.assertEqual(client.read(paper)["affiliations"], result["affiliations"])

    def test_html_scripts_are_not_evidence(self):
        self.assertEqual(_plain("<p>Actual finding.</p><script>steal()</script><p>Second finding.</p>"), "Actual finding.\nSecond finding.")

    def test_ambiguous_title_requires_identifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = LiteratureClient(Path(tmp))
            client.search = lambda *args, **kwargs: [_paper("Shared research method alpha"), _paper("Shared research method beta")]
            with self.assertRaises(LiteratureError):
                client.resolve("Shared research method")

    def test_arxiv_fallback_preserves_doi_identity(self):
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        page = b'<li class="arxiv-result"><p class="title">Planning-oriented Autonomous Driving</p><a href="https://arxiv.org/abs/2212.10156">abs</a><span class="abstract-full">Recovered abstract.</span></li>'
        def fetch(url):
            if "crossref" in url: return json.dumps({"message":{"DOI":"10.1109/x","title":["Planning-oriented Autonomous Driving"],"author":[]}}).encode()
            if "semanticscholar" in url: raise LiteratureError("unavailable")
            return atom if "export.arxiv.org" in url else page
        with tempfile.TemporaryDirectory() as tmp:
            paper = LiteratureClient(Path(tmp), fetcher=fetch).resolve("10.1109/x")
            self.assertEqual(paper["external_ids"]["arxiv"], "2212.10156")
            self.assertEqual(paper["id"], _paper("Planning-oriented Autonomous Driving", external_ids={"doi":"10.1109/x"})["id"])
            self.assertTrue(any(x["location"] == "Abstract" for x in paper["passages"]))

    def test_read_sparse_record_recovers_text_without_resolve(self):
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2001.12345</id><title>Synthetic recovery fixture</title><summary>A substantive abstract about updating a finite state under bounded memory.</summary><published>2020-01-01T00:00:00Z</published></entry></feed>'
        body = ("<h1>Introduction</h1>" + "<p>" + "This synthetic method updates bounded memory using an explicit correction. " * 80 + "</p>").encode()
        def fetch(url):
            if "semanticscholar" in url: raise LiteratureError("unavailable")
            return atom if "export.arxiv.org" in url else body
        with tempfile.TemporaryDirectory() as tmp:
            client = LiteratureClient(Path(tmp), fetcher=fetch)
            original = _paper("Synthetic recovery fixture", external_ids={"doi":"10.1000/example"})
            # Direct read models resuming an old metadata-only working record.
            recovered = client.read(original)
            self.assertEqual(recovered["id"], original["id"])
            self.assertEqual(recovered["source_status"], "fulltext")
            self.assertTrue(any(p["location"] == "Abstract" and p["text"] == recovered["abstract"] for p in recovered["passages"]))
            self.assertEqual(recovered["external_ids"]["arxiv"], "2001.12345")
            self.assertTrue(any("bounded memory" in p["text"] for p in recovered["passages"]))

    def test_title_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = LiteratureClient(Path(tmp), fetcher=lambda _: b"")
            client._json = lambda _: {"data": []}
            client._arxiv = lambda **_: [_paper("Planning-oriented Autonomous Driving Systems", external_ids={"arxiv":"2212.10156"}, abstract="Wrong")]
            paper = _paper("Planning-oriented Autonomous Driving", external_ids={"doi":"10.1109/x"})
            result = client._enrich_alternate_sources(paper)
            self.assertNotIn("arxiv", result["external_ids"])
            self.assertEqual(result["id"], paper["id"])


    def test_search_newest_filters_unknown_and_old_years(self):
        client = LiteratureClient(Path(tempfile.mkdtemp()), fetcher=lambda _: b"")
        client._json = lambda url: {"data": [
            {"paperId":"a","title":"New","year":2024,"abstract":"","externalIds":{},"authors":[]},
            {"paperId":"b","title":"Old","year":2019,"abstract":"","externalIds":{},"authors":[]},
            {"paperId":"c","title":"Unknown","abstract":"","externalIds":{},"authors":[]}]}
        rows = client.search("bounded planning", year_from=2020, sort="newest")
        self.assertEqual([x["title"] for x in rows], ["New"])

    def test_related_direction_only_queries_requested_relation(self):
        client = LiteratureClient(Path(tempfile.mkdtemp()), fetcher=lambda _: b"")
        seen = []
        client._json = lambda url: (seen.append(url) or {"data": []})
        paper = _paper("Fixture", external_ids={"s2":"abc"})
        client.related(paper, direction="references")
        self.assertEqual(len(seen), 1)
        self.assertIn("/references?", seen[0])

    def test_related_recovers_identity_from_supported_canonical_urls(self):
        client = self._temp_client()
        seen = []
        client._json = lambda url: (seen.append(url) or {"data": []})
        client.related({"id": "legacy-arxiv", "title": "Legacy", "url": "https://arxiv.org/abs/2212.10156"}, direction="citations")
        client.related({"id": "legacy-doi", "title": "Legacy", "url": "https://doi.org/10.1109/CVPR52729.2023.01712"}, direction="references")
        self.assertEqual(len(seen), 2)
        self.assertIn("/paper/ARXIV%3A2212.10156/citations?", seen[0])
        self.assertIn("/paper/DOI%3A10.1109%2FCVPR52729.2023.01712/references?", seen[1])


    def test_provider_date_parameters_and_broad_search_mode(self):
        import urllib.parse
        client = self._temp_client()
        urls = []
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        def fetch(url):
            urls.append(url)
            if "semanticscholar" in url: return json.dumps({"data": []}).encode()
            if "export.arxiv.org" in url: return atom
            return json.dumps({"message":{"items":[]}}).encode()
        client.fetcher = fetch
        client.search("rare planning", year_from=2020, sort="newest")
        s2 = urllib.parse.parse_qs(urllib.parse.urlsplit(urls[0]).query)
        self.assertEqual(s2.get("year"), ["2020-"])
        self.assertNotIn("year:", s2.get("query", [""])[0])
        arxiv = urllib.parse.parse_qs(urllib.parse.urlsplit(next(u for u in urls if "export.arxiv" in u)).query)
        self.assertIn("submittedDate:[202001010000 TO ", arxiv["search_query"][0])
        self.assertNotIn("submittedDate", arxiv)

    def test_arxiv_html_submitted_date_and_author_fixture(self):
        client = self._temp_client(); client.fetcher = (lambda url: (
            b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>' if "export.arxiv" in url else
            b'<li class="arxiv-result"><p class="title">Fixture</p><a href="https://arxiv.org/abs/1234.5678">abs</a><span class="authors"><a href="/search/?searchtype=author&query=A">Alice Example</a></span><span class="submission-history">Submitted 20 December, 2022</span><span class="abstract-full">Abstract fixture.</span></li>'))
        rows = client._arxiv(query="Fixture", limit=1, exact_title=False)
        self.assertEqual(rows[0]["date"], "2022-12-20")
        self.assertEqual(rows[0]["authors"], ["Alice Example"])

    def test_direction_without_identity_does_not_search(self):
        client = self._temp_client()
        client.search = lambda *args, **kwargs: self.fail("must not fallback to search")
        with self.assertRaises(LiteratureError): client.related(_paper("No identity"), direction="citations")

    def test_invalid_sort_is_rejected(self):
        client = self._temp_client()
        with self.assertRaises(LiteratureError):
            client.search("fixture", sort="oldest")


    def test_year_window_is_encoded_and_applied(self):
        import urllib.parse
        client = self._temp_client(); urls = []
        def fetch(url):
            urls.append(url)
            if "semanticscholar" in url: return json.dumps({"data":[{"paperId":"a","title":"Old","year":2019,"externalIds":{},"authors":[]},{"paperId":"b","title":"Inside","year":2021,"externalIds":{},"authors":[]},{"paperId":"c","title":"Future","year":2024,"externalIds":{},"authors":[]}]}).encode()
            return b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        client.fetcher = fetch
        rows = client.search("window", year_from=2020, year_to=2022)
        self.assertEqual([x["title"] for x in rows], ["Inside"])
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(urls[0]).query)
        self.assertEqual(query["year"], ["2020-2022"])


    def test_arxiv_affiliation_parser_handles_class_order_nested_links_and_false_positives(self):
        html = b"""
        <div class="ltx_authors"><span class="ltx_personname">Body Institution</span></div>
        <span class="ltx_role_affiliation ltx_contact"><span>Affiliation:</span><a href="https://example.org">Linked Institute</a><sup>1</sup></span>
        <span class="ltx_contact ltx_role_affiliation"><span class="label">Affiliation:</span>Plain Institute</span>
        <span class="ltx_contact"><span>Affiliation:</span>Not an affiliation</span>
        """
        rows = LiteratureClient._arxiv_html_affiliations(html, "https://arxiv.org/html/fixture")
        self.assertEqual([row["name"] for row in rows], ["Linked Institute", "Plain Institute"])
        self.assertTrue(all(row["quote"] == row["name"] and row["source_url"].endswith("fixture") for row in rows))



if __name__ == "__main__":
    unittest.main()
