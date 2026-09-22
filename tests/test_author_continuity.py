import copy
import json
import tempfile
import unittest
from pathlib import Path

from deepanalyze.engine import _annual_candidates, _author_continuity, ResearchEngine
from deepanalyze.literature import LiteratureClient
from deepanalyze.graph import build_snapshot
from tests.test_yearly_discovery import candidate


class AuthorContinuityTests(unittest.TestCase):
    def corpus(self):
        anchor = {"id": "anchor", "title": "Seed", "year": 2023, "authors": ["Example Author"], "author_ids": ["s2:11"]}
        papers = {"anchor": anchor}
        for prefix, identities in (("same", ["s2:11"]), ("outside", ["s2:99"])):
            for i in range(8):
                paper = candidate(f"{prefix}{i}", 2024)
                paper.update(authors=["Example Author"], author_ids=identities)
                papers[paper["id"]] = paper
        return anchor, papers

    def test_persistent_ids_override_ambiguous_matching_names(self):
        seed, papers = self.corpus()
        self.assertGreater(_author_continuity(papers["same0"], papers, ["anchor"])["score"], 0)
        self.assertEqual(_author_continuity(papers["outside0"], papers, ["anchor"])["score"], 0)
        papers["same0"]["author_ids"] = None
        signal = _author_continuity(papers["same0"], papers, ["anchor"])
        self.assertEqual(signal["basis"], "name_overlap_unverified")

    def test_earlier_or_undated_work_gets_no_successor_boost(self):
        seed, papers = self.corpus()
        for year in (2022, 2023, None):
            paper = {**papers["same0"], "year": year}
            self.assertEqual(_author_continuity(paper, papers, ["anchor"])["score"], 0)
        papers["anchor"]["date"] = "2023-01-02"
        paper = {**papers["same0"], "year": 2023, "date": "2023-06-01"}
        self.assertGreater(_author_continuity(paper, papers, ["anchor"])["score"], 0)

    def test_author_overlap_never_bypasses_direct_citation_boundary(self):
        seed, papers = self.corpus()
        papers["same0"]["citation_links"] = []
        self.assertEqual(_author_continuity(papers["same0"], papers, ["anchor"])["score"], 0)
        selected, _ = _annual_candidates(papers, {"anchor"}, ["anchor"], seed, 12, {}, now_year=2024)
        self.assertNotIn("same0", selected)

    def test_author_slots_leave_two_thirds_for_other_teams(self):
        seed, papers = self.corpus()
        selected, _ = _annual_candidates(papers, {"anchor"}, ["anchor"], seed, 12, {}, now_year=2024)
        # Two years, with six places per year; the empty seed-year allocation
        # is not reassigned. Two of six slots favor author continuity.
        self.assertEqual(len(selected), 6)
        self.assertEqual(sum(key.startswith("same") for key in selected), 2)
        self.assertEqual(sum(key.startswith("outside") for key in selected), 4)
        self.assertTrue(all("author_continuity" in item for item in selected.values()))

    def test_one_candidate_budget_rotates_author_preference(self):
        seed, papers = self.corpus()
        offered, read, keys = {}, {"anchor"}, []
        for _ in range(3):
            selected, _ = _annual_candidates(papers, read, ["anchor"], seed, 1, offered, now_year=2024)
            key = next(iter(selected)); keys.append(key); read.add(key)
        self.assertTrue(keys[0].startswith("same"))
        self.assertTrue(all(key.startswith("outside") for key in keys[1:]))

    def test_previously_seen_author_candidate_does_not_displace_unseen_work(self):
        seed, papers = self.corpus()
        offered = {key: 4 for key in papers if key.startswith("same")}
        selected, _ = _annual_candidates(papers, {"anchor"}, ["anchor"], seed, 1, offered, now_year=2024)
        self.assertTrue(next(iter(selected)).startswith("outside"))

    def test_year_balance_survives_large_author_cluster(self):
        seed, papers = self.corpus()
        for item in papers.values():
            if item["id"] != "anchor": item["year"] = 2026
        for year in (2024, 2025): papers[str(year)] = candidate(str(year), year)
        selected, _ = _annual_candidates(papers, {"anchor"}, ["anchor"], seed, 8, {}, now_year=2026)
        self.assertTrue({2024, 2025, 2026} <= {item["year"] for item in selected.values()})

    def test_author_ids_survive_metadata_cache_and_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            client = LiteratureClient(Path(folder))
            paper = client._s2_paper({"paperId": "synthetic", "title": "Public synthetic source", "year": 2020,
                                     "authors": [{"name": "Example Author", "authorId": "11"}], "externalIds": {}})
            self.assertEqual(paper["author_ids"], ["s2:11"])
            old_cache = {**copy.deepcopy(paper), "author_ids": [], "passages": [], "source_status": "fulltext"}
            self.assertEqual(client._reuse_read(old_cache, paper)["author_ids"], ["s2:11"])
            snapshot = build_snapshot({"nodes": [{"id": paper["id"]}], "groups": [], "edges": []}, {paper["id"]: paper}, None, paper["id"], "scope", 1)
            self.assertEqual(snapshot["nodes"][0]["author_ids"], ["s2:11"])


if __name__ == "__main__": unittest.main()
