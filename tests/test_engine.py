import copy
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from deepanalyze.engine import ResearchEngine, _balanced_selection, _Stop, _time_windows
from deepanalyze.schemas import normalize_config
from deepanalyze.store import RunStore


class FakeLiterature:
    def __init__(self):
        self.read_counts = {}
        self.queries = []
        self.papers = {
            f"p{index}": {
                "id": f"p{index}", "title": f"Synthetic paper {index}", "year": 2020 + index,
                "date": f"{2020 + index}-01-01", "url": f"https://example.org/p{index}",
                "abstract": f"This synthetic source {index} changes a bounded table operation.",
                "authors": [], "affiliations": [], "source_status": "abstract_only",
                "passages": [],
            } for index in range(6)
        }

    def resolve(self, seed):
        return copy.deepcopy(self.papers["p0"])

    def related(self, paper, limit=10, *, direction="both", offset=0):
        """Return only direct citation neighbors with verifiable provenance."""
        anchor_id = paper["id"]
        candidates = []
        for key, candidate in self.papers.items():
            if key in {anchor_id, "p0"}:
                continue
            if direction == "citations" and candidate.get("year", 0) <= paper.get("year", 0):
                continue
            if direction == "references" and candidate.get("year", 0) >= paper.get("year", 0):
                continue
            item = copy.deepcopy(candidate)
            item["citation_links"] = [{
                "anchor_id": anchor_id,
                "direction": "cites_anchor" if direction == "citations" else "cited_by_anchor",
                "source_url": f"https://api.semanticscholar.org/graph/v1/paper/{anchor_id}/{direction}",
            }]
            candidates.append(item)
        return candidates[offset:offset + limit]

    def search(self, query, limit=10, *, year_from=None, year_to=None, sort="relevance"):
        self.queries.append(query)
        eligible = [paper for paper in self.papers.values() if paper["id"] != "p0" and (year_from is None or paper.get("year", 0) >= year_from) and (year_to is None or paper.get("year", 9999) <= year_to)]
        eligible.sort(key=lambda paper: (paper.get("year", 0), paper["id"]), reverse=sort == "newest")
        return [copy.deepcopy(paper) for paper in eligible[:limit]]

    def read(self, paper):
        paper = copy.deepcopy(paper)
        self.read_counts[paper["id"]] = self.read_counts.get(paper["id"], 0) + 1
        paper["source_status"] = "fulltext"
        paper["passages"] = [{"id": paper["id"] + "_source", "text": paper["abstract"], "location": "Synthetic section", "url": paper["url"]}]
        return paper


class FakeProvider:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.fail:
            raise RuntimeError("SECRET-api-key and C:\\private\\profile must never leak")
        data = json.loads(prompt.split("\nDATA:\n", 1)[1])
        if "relation_checks" in data:
            return {"data": {"reviews": [{"id": item["id"], "status": "supported", "reason": "Synthetic independent check.", "missing_evidence": ""}
                                           for item in data["relation_checks"]]}, "usage": {}}
        if "unread_candidates" in data:
            result = {
                "scope": "Follow the synthetic seed's bounded table problem.",
                "queries": ["bounded table missing corrections"], "challenges": ["Check retained-state assumptions."],
                "selected_ids": [paper["id"] for paper in data["unread_candidates"]][:data["max_selected_ids"]],
            }
        else:
            known = {n["id"]: copy.deepcopy(n) for n in data["current_structure"].get("nodes", [])}
            dates = {key: (n.get("year") or 0, n.get("date") or "", key) for key, n in known.items()}
            for paper in data["source_packets"]:
                known[paper["id"]] = {"id": paper["id"], "short_name": paper["id"], "group_ids": ["table"],
                    "problem": "Earlier retained tables omit corrections.", "mechanism": "Change the bounded table update.",
                    "solves": "Handle the stated update case.", "results": "Synthetic observation only.",
                    "limitations": ["Capacity remains bounded."], "assumptions": [], "uncertainties": [],
                    "evidence": [{"id": paper["id"] + "_ev", "quote": paper["passages"][0]["text"]}]}
                dates[paper["id"]] = (paper.get("year") or 0, paper.get("date") or "", paper["id"])
            nodes = list(known.values())
            ids = sorted(known, key=lambda key: dates[key])
            refs = {key: known[key]["evidence"][0]["id"] for key in ids if known[key].get("evidence")}
            pairs = list(zip(ids, ids[1:]))
            edges = [{"source": first, "target": second, "kind": "addresses", "status": "supported",
                      "problem": "Earlier retained tables omit corrections.", "mechanism": "Change the bounded table update.",
                      "consequence": "The next synthetic design tests the missing correction case.",
                      "evidence_ids": [refs[first], refs[second]], "rationale": "Synthetic fixture only.", "conditions": [],
                      "historical_influence": "not_claimed"}
                     for first, second in pairs if first in refs and second in refs]
            group = {"id": "table", "label": "Table updates", "description": "Synthetic grouping",
                     "core_concept": "Bounded table correction", "label_nouns": ["table", "updates"],
                     "explanatory_claim": {"constraint": "A bounded table retains incomplete corrections.",
                        "mechanism": "Revise the retained update rule.", "consequence": "Some correction cases become representable."},
                     "member_ids": ids, "merge_from": [], "separation_reason": "",
                     "common_problem": "Bounded corrections", "progression": "Revise one retained update rule.", "open_problem": "Capacity limits",
                     "spine": [{"source": a, "target": b, "claim_connection": "Revises the retained update rule."} for a,b in pairs],
                     "member_support": [{"paper_id": key, "claim_connection": "Tests a correction within the bounded retained table.",
                                          "evidence_ids": [refs[key]]} for key in ids if key in refs]}
            result = {"update_mode": "incremental", "scope": data["fixed_scope"], "groups": [group],
                      "dispositions": [{"paper_id": key, "status": "included", "reason": "Synthetic fixture."} for key in ids],
                      "comparisons": [], "nodes": nodes, "edges": edges, "gaps": [], "review_notes": ["Synthetic provider test."]}
        return {"data": result, "usage": {}, "thread_id": "synthetic-thread"}


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = RunStore(Path(self.directory.name))

    def test_live_loop_caches_sources_and_saves_incremental_immutable_versions(self):
        provider, literature = FakeProvider(), FakeLiterature()
        run = self.store.create("Synthetic paper 0", {"max_iterations": 2, "read_per_round": 2})
        ResearchEngine(provider, literature, self.store).run(run["id"], threading.Event())
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["snapshots"]), 2)
        self.assertEqual(result["progress"]["model_calls"], 6)
        self.assertTrue(all(count == 1 for count in literature.read_counts.values()))
        self.assertEqual(len(literature.read_counts), 4)
        first = self.store.snapshot(run["id"], result["snapshots"][0]["id"])
        self.assertEqual(len(first["nodes"]), 2)
        self.assertEqual(len(result["latest_snapshot"]["nodes"]), 4)
        self.assertEqual(result["latest_snapshot"]["metrics"]["depth"], 3)
        self.assertEqual(literature.queries, [])

    def test_model_budget_does_not_publish_partial_synthesis(self):
        provider = FakeProvider()
        run = self.store.create("Synthetic paper 0", {"max_model_calls": 1})
        ResearchEngine(provider, FakeLiterature(), self.store).run(run["id"], threading.Event())
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(result["snapshots"], [])

    def test_provider_error_is_honest_and_does_not_leak_exception_details(self):
        run = self.store.create("Synthetic paper 0", {})
        ResearchEngine(FakeProvider(fail=True), FakeLiterature(), self.store).run(run["id"], threading.Event())
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["latest_snapshot"])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("private", json.dumps(result))

    def test_cancel_during_blocked_lookup_returns_without_publishing(self):
        entered, release, cancel = threading.Event(), threading.Event(), threading.Event()
        literature = FakeLiterature()
        original_resolve = literature.resolve

        def slow_resolve(seed):
            entered.set()
            release.wait(5)
            return original_resolve(seed)

        literature.resolve = slow_resolve
        run = self.store.create("Synthetic paper 0", {})
        engine = ResearchEngine(FakeProvider(), literature, self.store)
        worker = threading.Thread(target=engine.run, args=(run["id"], cancel))
        worker.start()
        self.assertTrue(entered.wait(2))
        cancel.set()
        worker.join(2)
        release.set()
        self.assertFalse(worker.is_alive())
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["snapshots"], [])

    def test_demo_has_no_network_or_model_calls_and_is_explicitly_synthetic(self):
        class Forbidden:
            def __getattr__(self, name):
                raise AssertionError("Demo must not access providers")

        run = self.store.create("Synthetic ledger", {"max_iterations": 2}, "demo")
        ResearchEngine(Forbidden(), Forbidden(), self.store).run(run["id"], threading.Event())
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["progress"]["model_calls"], 0)
        self.assertTrue(result["latest_snapshot"]["demo"])
        self.assertTrue(all(node["source_status"] == "synthetic_demo" for node in result["latest_snapshot"]["nodes"]))

    def test_engine_waits_for_provider_cleanup_after_cancellation(self):
        entered, cleaning, cleaned, release, cancel = (threading.Event() for _ in range(5))

        class CleaningProvider:
            def generate(self, prompt, **kwargs):
                entered.set()
                kwargs["cancel_event"].wait(2)
                cleaning.set()
                release.wait(2)
                cleaned.set()
                raise RuntimeError("Cancelled after transport cleanup.")

        run = self.store.create("Synthetic paper 0", {})
        worker = threading.Thread(target=ResearchEngine(CleaningProvider(), FakeLiterature(), self.store).run,
                                  args=(run["id"], cancel))
        worker.start()
        self.assertTrue(entered.wait(2))
        cancel.set()
        self.assertTrue(cleaning.wait(2))
        self.assertTrue(worker.is_alive())
        self.assertEqual(self.store.get(run["id"])["status"], "running")
        release.set()
        worker.join(2)
        self.assertTrue(cleaned.is_set())
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.store.get(run["id"])["status"], "stopped")

    def test_citation_counterexample_route_retains_space_in_candidate_pool(self):
        class Routes(FakeLiterature):
            def __init__(self):
                super().__init__()
                for index in (6, 7):
                    self.papers[f"p{index}"] = {**self.papers["p5"], "id": f"p{index}", "title": f"Synthetic paper {index}", "year": 2020 + (index % 7), "date": f"{2020 + (index % 7)}-01-01"}

            def related(self, paper, limit=10, *, direction="both", offset=0):
                candidates = []
                for key in ("p7", "p1", "p2", "p3", "p4", "p5", "p6"):
                    if key == paper["id"] or key == "p0":
                        continue
                    item = copy.deepcopy(self.papers[key])
                    item["citation_links"] = [{
                        "anchor_id": paper["id"],
                        "direction": "cites_anchor" if direction == "citations" else "cited_by_anchor",
                        "source_url": f"https://api.semanticscholar.org/graph/v1/paper/{paper['id']}/{direction}",
                    }]
                    candidates.append(item)
                return candidates[offset:offset + limit]

        provider = FakeProvider()
        run = self.store.create("Synthetic paper 0", {"max_iterations": 2, "read_per_round": 1, "candidates_per_round": 6})
        ResearchEngine(provider, Routes(), self.store).run(run["id"], threading.Event())
        self.assertEqual(self.store.get(run["id"])["status"], "completed")
        prompts = [json.loads(prompt.split("\nDATA:\n", 1)[1]) for prompt, _ in provider.calls]
        explored = [prompt for prompt in prompts if "unread_candidates" in prompt]
        self.assertTrue(any("p7" in {paper["id"] for paper in prompt["unread_candidates"]} for prompt in explored))
        self.assertLessEqual(len(explored[1]["unread_candidates"]), 6)

    def test_unreadable_seed_stops_before_model_spend(self):
        literature = FakeLiterature()
        literature.papers["p0"]["abstract"] = ""
        provider = FakeProvider()
        run = self.store.create("Synthetic paper 0", {})
        ResearchEngine(provider, literature, self.store).run(run["id"], threading.Event())
        self.assertEqual(self.store.get(run["id"])["status"], "needs_source")
        self.assertEqual(provider.calls, [])
        self.assertFalse(ResearchEngine._has_technical_content({"passages": [{
            "text": "Institution name and author affiliations. " * 5,
            "kind": "metadata_affiliation", "location": "Metadata"}]}))

    def test_thirty_reads_are_not_truncated_by_selection_helper(self):
        class ManySources(FakeLiterature):
            def __init__(self):
                super().__init__()
                for index in range(6, 40):
                    self.papers[f"p{index}"] = {**self.papers["p5"], "id": f"p{index}", "title": f"Synthetic paper {index}", "year": 2020 + (index % 7), "date": f"{2020 + (index % 7)}-01-01"}
            def related(self, paper, limit=10, *, direction="both", offset=0):
                candidates = []
                for candidate in self.papers.values():
                    if candidate["id"] in {paper["id"], "p0"}:
                        continue
                    item = copy.deepcopy(candidate)
                    item["citation_links"] = [{
                        "anchor_id": paper["id"],
                        "direction": "cites_anchor" if direction == "citations" else "cited_by_anchor",
                        "source_url": f"https://api.semanticscholar.org/graph/v1/paper/{paper['id']}/{direction}",
                    }]
                    candidates.append(item)
                return candidates[offset:offset + limit]
        literature = ManySources()
        run = self.store.create("Synthetic paper 0", {"max_iterations": 1, "read_per_round": 30,
            "candidates_per_round": 60, "max_model_calls": 12})
        ResearchEngine(FakeProvider(), literature, self.store).run(run["id"], threading.Event())
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["progress"]["read"], 30)
        self.assertEqual(len(literature.read_counts), 30)
        self.assertLessEqual(len(result["calls"]), 12)
        self.assertEqual(result["progress"]["model_calls"], len(result["calls"]))

    def test_small_corpus_compares_every_pair_and_packet_text_is_bounded(self):
        papers = list(FakeLiterature().papers.values())[:4]
        self.assertEqual(len(ResearchEngine._comparison_pairs(None, papers)), 6)
        for paper in papers:
            paper["passages"] = [{"id": "meta", "text": "Affiliation " * 200,
                                  "kind": "metadata_affiliation", "location": "Metadata"}] + [
                {"id": str(i), "text": "method limitations motivation " * 2000, "location": "Section"}
                for i in range(10)]
        packets = ResearchEngine._source_packets(papers, [], None)
        self.assertLessEqual(sum(len(p["text"]) for packet in packets for p in packet["passages"]), 70000)
        self.assertTrue(all(p["id"] != "meta" for packet in packets for p in packet["passages"]))

    def test_comparison_pairs_cover_each_new_source_without_old_old_regeneration(self):
        previous = {"nodes": [{"id": "old1", "year": 2020}, {"id": "old2", "year": 2021}], "comparisons": [{"source": "old1", "target": "old2"}]}
        packets = [{"id": "new1", "year": 2022, "is_new": True, "title": "new one", "passages": [{"text": "bounded table"}]},
                   {"id": "new2", "year": 2023, "is_new": True, "title": "new two", "passages": [{"text": "bounded table"}]}]
        pairs = ResearchEngine._comparison_pairs(previous, packets)
        self.assertTrue({"new1", "new2"}.issubset({item["source"] for pair in pairs for item in [pair]} | {item["target"] for item in pairs}))
        self.assertNotIn({"old1", "old2"}, [{item["source"], item["target"]} for item in pairs])

    def test_balanced_selection_iterates_individual_years(self):
        seed = {"id": "seed", "year": 2020}
        windows = _time_windows(seed, now_year=2026)
        self.assertEqual(windows, [(2020, 2021), (2022, 2023), (2024, 2026)])
        papers = {f"p{year}": {"id": f"p{year}", "year": year} for year in (2026, 2025, 2024, 2023, 2022, 2021)}
        from unittest.mock import patch
        with patch("deepanalyze.engine._time_windows", return_value=windows):
            selected = _balanced_selection(list(papers), papers, 3, seed, [])
        self.assertEqual({papers[key]["year"] for key in selected}, {2021, 2022, 2023})
        self.assertEqual(len(selected), 3)

    def test_repair_failure_preserves_draft_without_publishing_completion(self):
        for budget in (False, True):
            with self.subTest(budget=budget):
                class NeedsRepair(FakeProvider):
                    def generate(self, prompt, **kwargs):
                        data = json.loads(prompt.split("\nDATA:\n", 1)[1])
                        if "revision_feedback" in data:
                            self.calls.append((prompt, kwargs))
                            self.has_source_evidence = bool(data["source_packets"])
                            if budget:
                                raise _Stop("Synthetic budget exhausted during optional repair")
                            raise RuntimeError("Synthetic repair transport failure")
                        result = super().generate(prompt, **kwargs)
                        if "source_packets" in data:
                            result["data"]["groups"] = [{"id": n["id"], "label": n["id"], "member_ids": [n["id"]]}
                                for n in result["data"]["nodes"]]
                            for n in result["data"]["nodes"]: n["group_ids"] = [n["id"]]
                        return result
                provider = NeedsRepair()
                run = self.store.create("Synthetic paper 0", {"max_iterations": 1, "max_model_calls": 12})
                ResearchEngine(provider, FakeLiterature(), self.store).run(run["id"], threading.Event())
                result = self.store.get(run["id"])
                self.assertEqual(result["status"], "budget_exhausted" if budget else "failed")
                self.assertEqual(result["snapshots"], [])
                self.assertIsNone(result["latest_snapshot"])
                self.assertLess(len(provider.calls), 12)
                self.assertIn("revision_feedback", provider.calls[-1][0])
                self.assertTrue(provider.has_source_evidence)
                self.assertTrue(self.store.working(run["id"])["synthesis_draft"])

    def test_default_and_blank_model_select_luna_explicitly(self):
        self.assertEqual(normalize_config()["model"], "gpt-5.6-luna")
        self.assertEqual(normalize_config({"model": "  "})["model"], "gpt-5.6-luna")

    def test_budget_values_are_not_silently_expanded(self):
        for value in (0, -1, True, 101, "3"):
            with self.assertRaises(ValueError):
                normalize_config({"max_model_calls": value})


if __name__ == "__main__":
    unittest.main()
