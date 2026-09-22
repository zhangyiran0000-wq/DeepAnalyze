import copy
import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from deepanalyze.literature import LiteratureClient, READ_CACHE_VERSION, _paper


class ReadCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.client = LiteratureClient(self.directory, fetcher=lambda _: self.fail("Readable cache must not require a network request"))
        self.seed = _paper("Synthetic cache recovery", external_ids={"doi":"10.1234/cache"})

    def legacy(self, record, identifier=None):
        digest = hashlib.sha256((record["id"] + ":" + str(identifier)).encode()).hexdigest()
        path = self.directory / ("read_" + digest + ".json")
        path.write_text(json.dumps(record), encoding="utf-8")
        return path

    def fulltext(self):
        return {**copy.deepcopy(self.seed), "external_ids":{**self.seed["external_ids"], "arxiv":"2001.12345"},
                "source_status":"fulltext", "abstract":"A readable abstract about a synthetic bounded state correction mechanism.",
                "passages":[{"id":"source:method", "text":"This synthetic method corrects stored values using an explicitly bounded auxiliary table.", "location":"Method", "url":"https://arxiv.org/html/2001.12345"}]}

    def test_sparse_seed_reuses_legacy_fulltext_before_remote_recovery(self):
        self.legacy({**self.seed,"read_cache_version":2})
        self.legacy(self.fulltext(), "2001.12345")
        result = self.client.read(self.seed)
        self.assertEqual(result["id"], self.seed["id"])
        self.assertEqual(result["source_status"], "fulltext")
        self.assertEqual(result["external_ids"]["arxiv"], "2001.12345")
        self.assertTrue(result["cache_hit"])
        self.assertIn(self.fulltext()["passages"][0]["text"], [p["text"] for p in result["passages"]])
        # Both sparse and enriched identifiers now reuse the same canonical cache.
        self.assertEqual(self.client._read_target(self.seed), self.client._read_target(result))
        self.assertEqual(self.client.read(self.seed)["source_status"], "fulltext")

    def test_negative_cache_does_not_mask_newly_recovered_abstract(self):
        negative = {**self.seed,"read_cache_version":READ_CACHE_VERSION}
        self.client._save_read(self.client._read_target(self.seed), negative)
        abstract = "A newly recovered abstract supplies the missing technical motivation and mechanism."
        self.client._enrich_alternate_sources = lambda paper: _paper(paper["title"], external_ids=paper["external_ids"], abstract=abstract)
        result = self.client.read(self.seed)
        self.assertEqual(result["source_status"], "abstract_only")
        self.assertEqual(result["abstract"], abstract)
        self.assertTrue(any(p["text"] == abstract for p in result["passages"]))

    def test_same_title_with_conflicting_doi_is_not_reused(self):
        wrong = self.fulltext()
        wrong.update(id="a_different_paper", stable_original_id="a_different_paper", external_ids={"doi":"10.1234/different"})
        self.legacy(wrong, "2001.12345")
        self.client._enrich_alternate_sources = lambda paper: paper
        result = self.client.read(self.seed)
        self.assertEqual(result["source_status"], "metadata_only")
        self.assertEqual(result["abstract"], "")

    def test_exact_external_identifier_can_reuse_a_different_internal_id(self):
        cached = self.fulltext()
        cached.update(id="old_internal_id", stable_original_id="old_internal_id")
        self.legacy(cached, "2001.12345")
        result = self.client.read(self.seed)
        self.assertEqual(result["id"], self.seed["id"])
        self.assertEqual(result["source_status"], "fulltext")
        self.assertTrue(all(p["id"].startswith(self.seed["id"] + ":") for p in result["passages"]))

    def test_abstract_cache_hits_do_not_renew_freshness(self):
        record = _paper(self.seed["title"], external_ids=self.seed["external_ids"],
                        abstract="A sufficiently long abstract about synthetic technical source recovery and reuse.")
        path = self.legacy(record)
        old = time.time() - 120
        os.utime(path,(old,old))
        result = self.client.read(self.seed)
        self.assertTrue(result["cache_hit"])
        canonical = self.client._read_target(self.seed)
        self.assertAlmostEqual(canonical.stat().st_mtime, old, places=3)
        self.client.read(self.seed)
        self.assertAlmostEqual(canonical.stat().st_mtime, old, places=3)

    def test_new_abstract_is_not_discarded_by_fresh_empty_cache(self):
        self.legacy({**self.seed,"read_cache_version":READ_CACHE_VERSION})
        incoming = _paper(self.seed["title"], external_ids=self.seed["external_ids"],
                          abstract="A substantive new abstract supplied by a successful metadata lookup.")
        self.client._enrich_alternate_sources = lambda paper: paper
        result = self.client.read(incoming)
        self.assertEqual(result["abstract"], incoming["abstract"])
        self.assertEqual(result["source_status"], "abstract_only")
