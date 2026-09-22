import tempfile
import threading
import unittest
from pathlib import Path

from tests.test_engine import FakeLiterature, FakeProvider
from deepanalyze.store import RunStore
from deepanalyze.engine import ResearchEngine

from deepanalyze.engine import _annual_candidates


S2 = "https://api.semanticscholar.org/graph/v1/paper/anchor/citations"


def candidate(key, year=None, *, direction="cites_anchor", anchor="anchor"):
    item = {"id": key, "title": key, "year": year, "abstract": "evidence"}
    item["citation_links"] = [{
        "anchor_id": anchor,
        "direction": direction,
        "source_url": S2 if direction == "cites_anchor" else S2.replace("/citations", "/references"),
    }]
    return item


class YearlyDiscoveryTests(unittest.TestCase):
    def test_year_queue_does_not_follow_api_insertion_order(self):
        papers = {"anchor": candidate("anchor", 2023)}
        # Newest records are deliberately first, as in a citation endpoint's
        # front page; the annual queue should still cover each available year.
        for year in (2026, 2026, 2025, 2024, 2022, 2021):
            key = f"p{year}_{len(papers)}"
            papers[key] = candidate(key, year)
        fresh, cursor = _annual_candidates(
            papers, set(), ["anchor"], papers["anchor"], 6, {}, 0, now_year=2026
        )
        years = [item["year"] for item in fresh.values()]
        self.assertTrue({2024, 2025, 2026}.issubset(years))
        self.assertLessEqual(sum(year < 2023 for year in years), 1)
        self.assertIn(cursor, range(7))

    def test_candidates_require_exact_citation_provenance(self):
        papers = {
            "anchor": candidate("anchor", 2023),
            "good": candidate("good", 2024),
            "bad": {"id": "bad", "title": "bad", "year": 2025,
                    "citation_links": [{"anchor_id": "other", "direction": "cites_anchor", "source_url": S2}]},
            "search": {"id": "search", "title": "search", "year": 2026},
        }
        fresh, _ = _annual_candidates(
            papers, set(), ["anchor"], papers["anchor"], 10, {}, 0, now_year=2026
        )
        self.assertIn("good", fresh)
        self.assertNotIn("bad", fresh)
        self.assertNotIn("search", fresh)

    def test_repeated_offered_candidates_lose_to_unseen_same_year(self):
        papers = {"anchor": candidate("anchor", 2023),
                  "old": candidate("old", 2025), "new": candidate("new", 2025)}
        offered = {"old": 4, "new": 0}
        fresh, _ = _annual_candidates(
            papers, set(), ["anchor"], papers["anchor"], 1, offered, 0, now_year=2025
        )
        self.assertEqual(set(fresh), {"new"})
        self.assertEqual(offered["new"], 1)

    def test_unknown_year_is_not_counted_as_annual_coverage(self):
        papers = {"anchor": candidate("anchor", 2023),
                  "unknown": candidate("unknown", None),
                  "known": candidate("known", 2024)}
        papers["unknown"].pop("year")
        fresh, _ = _annual_candidates(
            papers, set(), ["anchor"], papers["anchor"], 1, {}, 0, now_year=2024
        )
        self.assertEqual(set(fresh), {"known"})

    def test_small_budget_rotates_year_cursor_across_rounds(self):
        papers = {"anchor": candidate("anchor", 2020)}
        for year in range(2021, 2027):
            papers[f"p{year}"] = candidate(f"p{year}", year)
        offered = {}
        first, cursor = _annual_candidates(
            papers, set(), ["anchor"], papers["anchor"], 2, offered, 0, now_year=2026
        )
        second, next_cursor = _annual_candidates(
            papers, set(first), ["anchor"], papers["anchor"], 2, offered, cursor, now_year=2026
        )
        self.assertTrue(first)
        self.assertTrue(second)
        self.assertNotEqual(set(first), set(second))
        self.assertNotEqual(cursor, next_cursor)

    def test_middle_years_survive_large_page_order(self):
        papers = {"anchor": candidate("anchor", 2023)}
        for index in range(1800):
            year = 2026 if index < 900 else (2024 if index < 1200 else 2025)
            papers[f"p{index}"] = candidate(f"p{index}", year)
        fresh, _ = _annual_candidates(
            papers, set(), ["anchor"], papers["anchor"], 12, {}, 0, now_year=2026
        )
        self.assertIn(2024, {item["year"] for item in fresh.values()})
        self.assertIn(2025, {item["year"] for item in fresh.values()})


    def test_engine_resumes_middle_years_after_first_paged_citation_page(self):
        class PagedLiterature(FakeLiterature):
            def __init__(self):
                super().__init__()
                self.papers = {"p0": {**self.papers["p0"], "year": 2023, "date": "2023-01-01",
                                      "abstract": "A technical planning source with measurable method evidence."}}
                self.pages = []

            def neighbor_page(self, paper, direction, *, offset=0, limit=100, metadata_only=False):
                if direction == "references":
                    return {"papers": [], "offset": offset, "next_offset": None}
                rows = []
                if offset < 1000:
                    start, end = offset, min(offset + limit, 1000)
                    years = [2026] * (end - start)
                    next_offset = 1000
                else:
                    start, end = offset - 1000, min(offset - 1000 + limit, 800)
                    years = [2024] * min(400, max(0, end - start)) + [2025] * max(0, end - start - 400)
                    next_offset = offset + len(years) if len(years) == limit and end < 800 else None
                for index, year in enumerate(years, start=start):
                    key = f"page-{offset}-{index}"
                    rows.append({"id": key, "title": key, "year": year,
                                 "date": f"{year}-01-01", "abstract": "Paged technical evidence.",
                                 "source_status": "abstract_only", "passages": [], "authors": [],
                                 "affiliations": [], "citation_links": [{
                                     "anchor_id": paper["id"], "direction": "cites_anchor",
                                     "source_url": f"https://api.semanticscholar.org/graph/v1/paper/{paper['id']}/citations"}]})
                self.pages.append((paper["id"], direction, offset, limit))
                return {"papers": rows, "offset": offset, "next_offset": next_offset}

        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(Path(directory))
            literature = PagedLiterature()
            run = store.create("Synthetic paper 0", {"max_iterations": 2, "read_per_round": 2,
                                                       "candidates_per_round": 30, "max_model_calls": 8})
            ResearchEngine(FakeProvider(), literature, store).run(run["id"], threading.Event())
            result = store.get(run["id"])
            self.assertIn(result["status"], {"completed", "synthesis_incomplete"})
            working = store.working(run["id"])
            self.assertTrue(any(year in {2024, 2025} for year in
                                (paper.get("year") for paper in working["papers"].values())))
            discovery = working["discovery"]
            seed_state = discovery["scan_state"]["p0"]["citations"]
            self.assertTrue(seed_state["exhausted"])
            self.assertGreaterEqual(seed_state["scanned"], 1800)
            self.assertTrue(any(row[2] == 1000 for row in literature.pages if row[0] == "p0"))
            coverage = {row["year"]: row for row in discovery["year_coverage"]}
            self.assertEqual(coverage[2024]["pool_status"], "available")
            self.assertEqual(coverage[2025]["pool_status"], "available")


if __name__ == "__main__":
    unittest.main()
