import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
import sys
import types

from deepanalyze.literature import LiteratureClient, LiteratureError, _paper


class SourceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = LiteratureClient(Path(self.temp.name))

    def test_arxiv_relevance_search_omits_invalid_sort_parameter(self):
        seen = []
        def fetch(url):
            seen.append(url)
            if "export.arxiv.org" in url:
                raise LiteratureError("API unavailable")
            args = parse_qs(urlsplit(url).query)
            self.assertNotIn("order", args)
            return b'<li class="arxiv-result"><p class="title">Synthetic source</p><a href="https://arxiv.org/abs/2001.12345">abs</a><span class="abstract-full">A substantive abstract for a bounded synthetic source.</span></li>'
        self.client.fetcher = fetch
        result = self.client._arxiv(query="Synthetic source", exact_title=True)
        self.assertEqual(result[0]["external_ids"]["arxiv"], "2001.12345")
        self.assertEqual(len(seen), 2)

    def test_exact_arxiv_id_uses_landing_page_when_api_fails(self):
        def fetch(url):
            if "export.arxiv.org" in url:
                raise LiteratureError("API unavailable")
            if url == "https://arxiv.org/abs/2001.12345":
                return b'<meta name="citation_title" content="Synthetic source"><meta name="citation_arxiv_id" content="2001.12345"><meta name="citation_abstract" content="A substantive source about correcting stored state under capacity constraints."><meta name="citation_pdf_url" content="https://arxiv.org/pdf/2001.12345">'
            self.fail("Unexpected provider call: " + url)
        self.client.fetcher = fetch
        result = self.client.resolve("2001.12345")
        self.assertEqual(result["source_status"], "abstract_only")
        self.assertTrue(result["abstract"])
        self.assertEqual(result["metadata_source"], "https://arxiv.org/abs/2001.12345")

    def test_publisher_fallback_recovers_pdf_with_original_doi_identity(self):
        original = _paper("Synthetic publisher source", external_ids={"doi": "10.18653/v1/2025.fixture.1"})
        content = "This synthetic method corrects stored values under a specific capacity limit."
        def fetch(url):
            if url == "https://aclanthology.org/2025.fixture.1/":
                return b'<meta name=citation_title content="Synthetic publisher source"><meta name=citation_doi content="10.18653/v1/2025.fixture.1"><meta name=citation_pdf_url content="https://aclanthology.org/2025.fixture.1.pdf"><div class="acl-abstract"><h5>Abstract</h5><span>A substantive abstract explains the bounded correction mechanism.</span></div>'
            if url == "https://aclanthology.org/2025.fixture.1.pdf":
                return b"synthetic pdf bytes"
            raise LiteratureError("Other provider unavailable")
        self.client.fetcher = fetch
        fake_pdf = types.ModuleType("pypdf")
        fake_pdf.PdfReader = lambda stream: types.SimpleNamespace(pages=[types.SimpleNamespace(extract_text=lambda: content)])
        with patch.dict(sys.modules, {"pypdf": fake_pdf}):
            result = self.client.read(original)
        self.assertEqual(result["id"], original["id"])
        self.assertEqual(result["source_status"], "fulltext")
        self.assertEqual(result["fulltext_url"], "https://aclanthology.org/2025.fixture.1.pdf")
        self.assertTrue(any(p["text"] == content and p["location"] == "PDF page 1" for p in result["passages"]))
        self.client.fetcher = lambda url: self.fail("Full text must be cached")
        self.assertTrue(self.client.read(original)["cache_hit"])

    def test_wrong_publisher_identity_cannot_supply_evidence(self):
        original = _paper("Synthetic publisher source", external_ids={"doi": "10.18653/v1/2025.fixture.1"})
        def fetch(url):
            if "aclanthology.org" in url:
                return b'<meta name=citation_title content="Synthetic publisher source"><meta name=citation_doi content="10.18653/v1/2025.fixture.2"><div class="acl-abstract">A plausible but incorrect paper abstract must never be used as evidence.</div>'
            raise LiteratureError("Unavailable")
        self.client.fetcher = fetch
        result = self.client.read(original)
        self.assertEqual(result["source_status"], "metadata_only")
        self.assertFalse(result["abstract"])

    def test_recovered_full_abstract_extends_cached_prefix_without_refetching(self):
        prefix = "This source provides a sufficiently long technical abstract about bounded state."
        short = _paper("Synthetic source", abstract=prefix, external_ids={"arxiv": "2001.12345"})
        self.client._save_read(self.client._read_target(short), short)
        incoming = {**short, "abstract": prefix + " A second sentence explains the mechanism."}
        self.client.fetcher = lambda url: self.fail("No download needed to extend an existing prefix")
        result = self.client.read(incoming)
        self.assertEqual(result["abstract"], incoming["abstract"])
        self.assertEqual(result["passages"][0]["text"], incoming["abstract"])

    def test_only_supported_publisher_links_are_accepted(self):
        self.client._landing_paper = lambda url: {"url": url}
        self.assertEqual(self.client.resolve("https://aclanthology.org/2025.fixture.1/")["url"],
                         "https://aclanthology.org/2025.fixture.1/")
        for url in ("https://aclanthology.org.evil.example/2025.fixture.1/",
                    "https://aclanthology.org@127.0.0.1/2025.fixture.1/"):
            with self.subTest(url=url), self.assertRaises(LiteratureError):
                self.client.resolve(url)


if __name__ == "__main__":
    unittest.main()
