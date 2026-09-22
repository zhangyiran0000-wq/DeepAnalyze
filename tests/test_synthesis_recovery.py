import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

from deepanalyze.engine import ResearchEngine, _compact_structure
from deepanalyze.graph import build_snapshot
from deepanalyze.server import Application
from deepanalyze.store import RunStore
from tests.test_engine import FakeLiterature, FakeProvider
from tests.test_synthesis_revision import OmittingProvider


class NoRetrieval:
    def __getattr__(self, name):
        raise AssertionError("Repair must not retrieve sources: " + name)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = RunStore(Path(self.temp.name))

    def failed_run(self):
        run = self.store.create("seed", {"max_iterations": 1, "read_per_round": 3, "max_model_calls": 4})
        ResearchEngine(OmittingProvider(99), FakeLiterature(), self.store).run(run["id"], threading.Event())
        # Reproduce a saved legacy run stopped by the former two-revision cap.
        result = self.store.get(run["id"])
        self.store.update(run["id"], config={**result["config"], "max_model_calls": 10},
                          status="synthesis_incomplete")
        return self.store.get(run["id"])

    def test_every_generated_attempt_is_saved_without_publishing_failure(self):
        run = self.failed_run()
        self.assertEqual(run["snapshots"], [])
        self.assertGreaterEqual(len(run["synthesis_attempts"]), 3)
        attempts = list((Path(self.temp.name)/"runs"/run["id"]/"analysis").glob("*.json"))
        self.assertEqual(len(attempts), len(run["synthesis_attempts"]))
        self.assertTrue(all(json.loads(p.read_text())["completion_status"] == "incomplete" for p in attempts))

    def test_repair_uses_only_saved_sources_and_preserves_original(self):
        original = self.failed_run()
        self.store.update(original["id"], config={**original["config"], "max_model_calls": 30})
        original = self.store.get(original["id"])
        original_work = self.store.working(original["id"])
        branch = self.store.retry_synthesis(original["id"])
        provider = FakeProvider()
        ResearchEngine(provider, NoRetrieval(), self.store).run(branch["id"], threading.Event())
        result = self.store.get(branch["id"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["progress"]["read"], 3)
        self.assertEqual(result["progress"]["model_calls"], len(provider.calls))
        self.assertLessEqual(len(provider.calls), 26)
        self.assertEqual(result["latest_snapshot"]["iteration"], 1)
        self.assertEqual(result["latest_snapshot"]["completion_status"], "complete")
        self.assertEqual(self.store.get(original["id"]), {**original, "recovery_child_id": branch["id"],
                         "updated_at": self.store.get(original["id"])["updated_at"]})
        self.assertEqual(self.store.working(original["id"]), original_work)
        payloads = [json.loads(p.split("\nDATA:\n", 1)[1]) for p, _ in provider.calls]
        self.assertFalse(any("unread_candidates" in p for p in payloads))
        self.assertTrue(any("revision_feedback" in p for p in payloads))
        self.assertTrue(any("relation_checks" in p for p in payloads))
        self.assertEqual(self.store.synthesis_budget(branch["id"])["model_calls_used"], 4 + len(provider.calls))

    def test_repair_uses_original_remaining_budget_and_keeps_failed_draft(self):
        original = self.failed_run()
        branch = self.store.retry_synthesis(original["id"])
        provider = OmittingProvider(99)
        provider.round = 1
        ResearchEngine(provider, NoRetrieval(), self.store).run(branch["id"], threading.Event())
        result = self.store.get(branch["id"])
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertEqual(result["progress"]["model_calls"], 6)
        self.assertEqual(result["snapshots"], [])
        self.assertEqual(len(self.store.working(branch["id"])["synthesis_draft"]["nodes"]), 3)

    def test_old_checkpoint_cannot_create_another_shared_budget_branch(self):
        original = self.failed_run()
        branch = self.store.retry_synthesis(original["id"])
        self.store.update(branch["id"], status="stopped")
        app = Application.__new__(Application)
        app.store = self.store
        self.assertFalse(app.run_detail(original["id"])["can_retry_synthesis"])
        for location in ("runs", "trash", "purged"):
            if location == "trash": self.store.trash(branch["id"])
            if location == "purged": self.store.purge_trash([branch["id"]], confirm=True)
            with self.subTest(location=location), self.assertRaisesRegex(ValueError, "already been continued"):
                self.store.retry_synthesis(original["id"])

    def test_recovery_cannot_reset_exhausted_calls_or_time(self):
        for limit in ("calls", "time"):
            with self.subTest(limit=limit):
                original = self.failed_run()
                progress = original["progress"]
                if limit == "calls":
                    progress["model_calls"] = 10
                else:
                    progress["elapsed_seconds"] = original["config"]["max_seconds"]
                self.store.update(original["id"], progress=progress)
                with self.assertRaisesRegex(ValueError, "budget is exhausted"):
                    self.store.retry_synthesis(original["id"])
                app = Application.__new__(Application)
                app.store = self.store
                self.assertFalse(app.run_detail(original["id"])["can_retry_synthesis"])

    def test_legacy_recovery_chain_counts_each_segment_once(self):
        root = self.failed_run()
        parent = root
        for calls in (3, 2):
            child = self.store.create("seed", {**root["config"], "max_model_calls": 3},
                                      parent={"run_id": parent["id"], "recovery": "synthesis"})
            self.store.update(child["id"], status="synthesis_incomplete",
                              progress={"model_calls": calls, "elapsed_seconds": 100})
            self.store.working(child["id"], self.store.working(root["id"]))
            parent = child
        budget = self.store.synthesis_budget(parent["id"])
        self.assertEqual(budget["model_calls_used"], 9)
        self.assertEqual(budget["remaining_model_calls"], 1)
        self.assertEqual(budget["limits"]["max_model_calls"], 10)
        branch = self.store.retry_synthesis(parent["id"])
        ResearchEngine(FakeProvider(), NoRetrieval(), self.store).run(branch["id"], threading.Event())
        budget = self.store.synthesis_budget(branch["id"])
        self.assertEqual(budget["model_calls_used"], 10)
        self.assertEqual(budget["remaining_model_calls"], 0)
        self.assertEqual(budget["iteration_limit"], 1)

    def test_completed_call_time_is_a_floor_after_interruption(self):
        run = self.store.create("seed", {})
        call_id = self.store.begin_call(run["id"], "synthesis", "fake", 1, 10)
        self.store.finish_call(run["id"], call_id, "completed")
        record = self.store.get(run["id"])
        record["calls"][0]["elapsed_seconds"] = 42.0
        self.store._write(self.store._directory(run["id"]) / "run.json", record)
        budget = self.store.synthesis_budget(run["id"])
        self.assertEqual(budget["elapsed_seconds_used"], 42.0)
        self.assertEqual(budget["model_calls_used"], 1)

    def test_recovery_uses_only_remaining_time(self):
        root = self.failed_run()
        self.store.update(root["id"], progress={**root["progress"], "elapsed_seconds": root["config"]["max_seconds"] - 1})
        branch = self.store.retry_synthesis(root["id"])
        provider = FakeProvider()
        ResearchEngine(provider, NoRetrieval(), self.store).run(branch["id"], threading.Event())
        self.assertLessEqual(provider.calls[0][1]["timeout"], 1)

    def test_repaired_round_continues_original_exploration_rounds(self):
        root = self.failed_run()
        self.store.update(root["id"], config={**root["config"], "max_iterations": 2})
        branch = self.store.retry_synthesis(root["id"])
        provider = FakeProvider()
        ResearchEngine(provider, FakeLiterature(), self.store).run(branch["id"], threading.Event())
        result = self.store.get(branch["id"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual([s["iteration"] for s in result["snapshots"]], [2])
        discoveries = [json.loads(p.split("\nDATA:\n", 1)[1]) for p, _ in provider.calls if "unread_candidates" in p]
        self.assertEqual(len(discoveries), 1)
        self.assertTrue(discoveries[0]["evidence_tasks"])
        self.assertTrue({"p0", "p1", "p2"}.issubset({n["id"] for n in result["latest_snapshot"]["nodes"]}))

    def test_bounded_review_windows_eventually_cover_all_unresolved_sources(self):
        ids = ["seed", *map(str, range(14))]
        snapshot = {"seed_id": "seed", "nodes": [{"id": key} for key in ids], "groups": [],
                    "synthesis_quality": {"unconnected_source_ids": ids[1:]}}
        papers = {key: {} for key in ids}
        reviewed = {}
        for _ in range(3):
            selected = ResearchEngine._revision_source_ids(snapshot, papers, reviewed)
            self.assertLessEqual(len(selected), 6)
            self.assertIn("seed", selected)
            for key in selected:
                reviewed[key] = reviewed.get(key, 0) + 1
        self.assertEqual(set(reviewed), set(ids))

    def test_public_detail_exposes_analysis_not_private_sources(self):
        run = self.failed_run()
        working = self.store.working(run["id"])
        working["papers"]["private"] = {"secret": "private extraction sentinel"}
        working["synthesis_draft"]["private_debug"] = "private extraction sentinel"
        self.store.working(run["id"], working)
        app = Application.__new__(Application)
        app.store = self.store
        detail = app.run_detail(run["id"])
        self.assertTrue(detail["can_retry_synthesis"])
        self.assertEqual(len(detail["working_snapshot"]["nodes"]), 3)
        self.assertNotIn("private extraction sentinel", json.dumps(detail))
        self.assertEqual(detail["snapshots"], [])

    def test_compact_context_retains_referenced_quotes_beyond_first_two(self):
        quotes = [{"id": f"e{i}", "quote": str(i)*900, "verified": True} for i in range(5)]
        snapshot = {"nodes": [{"id": "a", "evidence": quotes}], "groups": [{"member_support": [{"paper_id": "a", "evidence_ids": ["e4"]}]}], "edges": [{"evidence_ids": ["e3"]}]}
        compact = _compact_structure(snapshot)["nodes"][0]
        self.assertEqual([e["id"] for e in compact["evidence"]], ["e0", "e1", "e3", "e4"])
        self.assertEqual(compact["evidence"][-1]["quote"], quotes[-1]["quote"])
        self.assertEqual(compact["available_evidence_ids"], ["e0", "e1", "e2", "e3", "e4"])

    def test_repair_keeps_broken_source_and_anchor_together(self):
        snapshot = {"seed_id": "seed", "nodes": [{"id": k, "evidence": []} for k in ["seed", *map(str, range(9))]],
                    "groups": [{"member_support": [{"paper_id": "8", "evidence_ids": ["missing"]}]}],
                    "synthesis_quality": {"unconnected_source_ids": list(map(str, range(9)))}}
        ids = ResearchEngine._revision_source_ids(snapshot, {n["id"]: n for n in snapshot["nodes"]})
        self.assertEqual(len(ids), 6)
        self.assertEqual(ids[0], "8")
        self.assertIn("seed", ids)


class PassageReferenceTests(unittest.TestCase):
    def fixture(self):
        papers = {key: {"id": key, "title": key, "year": 2020+i, "date": f"{2020+i}-01-01", "passages": [
            {"id": key+":passage", "text": "This is the complete supplied method passage for source " + key,
             "location": "Method", "url": "https://example.org/"+key}]} for i,key in enumerate(("a", "b"))}
        proposal = {"groups": [{"id": "g", "member_ids": ["a", "b"], "member_support": [
            {"paper_id": key, "claim_connection": "Known source", "evidence_ids": [key+":passage"]} for key in papers]}],
            "nodes": [{"id": key, "group_ids": ["g"], "evidence": []} for key in papers],
            "edges": [{"source": "a", "target": "b", "kind": "addresses", "status": "supported",
                       "problem": "Specific retained state limitation", "mechanism": "A changed state update", "evidence_ids": ["a:passage", "b:passage"]}]}
        return papers, proposal

    def test_short_exact_source_passage_reference_is_visible_and_attributed(self):
        papers, proposal = self.fixture()
        result = build_snapshot(proposal, papers, None, "a", "scope", 1)
        self.assertEqual(result["edges"][0]["status"], "supported")
        for node in result["nodes"]:
            self.assertEqual(node["evidence"][0]["quote"], papers[node["id"]]["passages"][0]["text"])
            self.assertTrue(node["evidence"][0]["verified"])

    def test_foreign_missing_or_long_passages_do_not_prove_a_link(self):
        for mode in ("foreign", "missing", "long", "metadata"):
            with self.subTest(mode=mode):
                papers, proposal = self.fixture()
                if mode == "foreign": proposal["edges"][0]["evidence_ids"] = ["a:passage"]
                if mode == "missing": papers["b"]["passages"] = []
                if mode == "long": papers["b"]["passages"][0]["text"] = "long passage "*300
                if mode == "metadata": papers["b"]["passages"][0]["kind"] = "metadata_affiliation"
                result = build_snapshot(proposal, papers, None, "a", "scope", 1)
                self.assertEqual(result["edges"][0]["status"], "hypothesis")


if __name__ == "__main__": unittest.main()
