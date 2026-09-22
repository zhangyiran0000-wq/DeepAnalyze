import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

from deepanalyze.engine import ResearchEngine, _explanation_complete
from deepanalyze.store import RunStore
from tests.test_engine import FakeLiterature, FakeProvider


class OmittingProvider(FakeProvider):
    def __init__(self, fail_revisions=0, disposition="deferred", fail_round=1):
        super().__init__()
        self.fail_revisions, self.disposition, self.fail_round = fail_revisions, disposition, fail_round
        self.round = 0
        self.attempt = 0

    def generate(self, prompt, **kwargs):
        data = json.loads(prompt.split("\nDATA:\n", 1)[1])
        result = super().generate(prompt, **kwargs)
        if "unread_candidates" in data:
            self.round += 1
            self.attempt = 0
            return result
        if "relation_checks" in data:
            return result
        self.attempt = data.get("revision_feedback", {}).get("attempt", self.attempt)
        attempt = self.attempt
        if self.round < self.fail_round or attempt > self.fail_revisions:
            return result
        payload = result["data"]
        key = payload["groups"][0]["member_ids"][-1]
        if key == "p0": return result
        payload["nodes"] = [n for n in payload["nodes"] if n["id"] != key]
        payload["edges"] = [e for e in payload["edges"] if key not in (e["source"], e["target"])]
        for group in payload["groups"]:
            group["member_ids"] = [k for k in group["member_ids"] if k != key]
            group["member_support"] = [r for r in group["member_support"] if r["paper_id"] != key]
            group["spine"] = [e for e in group["spine"] if key not in (e["source"], e["target"])]
        for d in payload["dispositions"]:
            if d["paper_id"] == key: d["status"] = self.disposition
        return result


class SynthesisRevisionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = RunStore(Path(self.folder.name))

    def run_engine(self, provider, **config):
        run = self.store.create("seed", {"max_iterations": 1, "read_per_round": 3, **config})
        ResearchEngine(provider, FakeLiterature(), self.store).run(run["id"], threading.Event())
        return self.store.get(run["id"])

    def test_revision_can_recover_and_only_then_publish(self):
        for failed in (0, 1, 3, 5):
            with self.subTest(failed=failed):
                provider = OmittingProvider(fail_revisions=failed)
                result = self.run_engine(provider)
                self.assertEqual(result["status"], "completed")
                self.assertLess(result["progress"]["model_calls"], result["config"]["max_model_calls"])
                self.assertEqual(len(result["snapshots"]), 1)
                snapshot = result["latest_snapshot"]
                self.assertEqual(snapshot["completion_status"], "complete")
                self.assertEqual(len(snapshot["nodes"]), 3)
                feedback = [json.loads(p.split("\nDATA:\n",1)[1]) for p,_ in provider.calls if "revision_feedback" in p]
                self.assertTrue(feedback[0]["source_packets"])
                self.assertLessEqual(len(feedback[0]["revision_feedback"]["required_paper_ids"]), 2)
                self.assertGreater(max(f["revision_feedback"]["attempt"] for f in feedback), failed)

    def test_only_total_call_budget_stops_incomplete_revisions(self):
        for budget, calls in ((2, 2), (3, 3), (10, 10)):
            for disposition in ("deferred", "out_of_scope"):
                with self.subTest(budget=budget, disposition=disposition):
                    result = self.run_engine(OmittingProvider(99, disposition), max_model_calls=budget)
                    self.assertEqual(result["status"], "budget_exhausted")
                    self.assertEqual(result["progress"]["model_calls"], calls)
                    self.assertEqual(result["snapshots"], [])
                    draft = self.store.working(result["id"])["synthesis_draft"]
                    self.assertEqual(len(draft["nodes"]), 3)
                    self.assertEqual(draft["completion_status"], "incomplete")

    def test_automatic_revisions_honor_user_stop(self):
        cancel = threading.Event()
        class CancellingProvider(OmittingProvider):
            def generate(self, prompt, **kwargs):
                result = super().generate(prompt, **kwargs)
                data = json.loads(prompt.split("\nDATA:\n", 1)[1])
                if data.get("revision_feedback", {}).get("attempt") == 4:
                    cancel.set()
                return result
        run = self.store.create("seed", {"max_iterations": 1, "read_per_round": 3})
        provider = CancellingProvider(99)
        ResearchEngine(provider, FakeLiterature(), self.store).run(run["id"], cancel)
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "stopped")
        self.assertLess(result["progress"]["model_calls"], result["config"]["max_model_calls"])
        self.assertEqual(result["snapshots"], [])
        self.assertTrue(self.store.working(run["id"])["synthesis_draft"])

    def test_automatic_revisions_honor_elapsed_time(self):
        from unittest.mock import patch
        elapsed = [0.0]
        class TimingProvider(OmittingProvider):
            def generate(self, prompt, **kwargs):
                result = super().generate(prompt, **kwargs)
                data = json.loads(prompt.split("\nDATA:\n", 1)[1])
                if data.get("revision_feedback", {}).get("attempt") == 4:
                    elapsed[0] = 10.0
                return result
        with patch("deepanalyze.engine.time.monotonic", side_effect=lambda: elapsed[0]):
            result = self.run_engine(TimingProvider(99), max_seconds=10)
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertIn("elapsed-time", result["stop_reason"])
        self.assertLess(result["progress"]["model_calls"], result["config"]["max_model_calls"])
        self.assertTrue(self.store.working(result["id"])["synthesis_draft"])

    def test_individually_explained_islands_do_not_count_as_a_complete_tree(self):
        from deepanalyze.graph import build_snapshot
        lib = FakeLiterature()
        papers = {key: lib.read(value) for key,value in list(lib.papers.items())[:4]}
        packets = ResearchEngine._source_packets(list(papers.values()), [], None)
        prompt = ResearchEngine._synthesis_prompt("scope", None, packets, {})
        proposal = FakeProvider().generate(prompt)["data"]
        first, second = copy.deepcopy(proposal["groups"][0]), copy.deepcopy(proposal["groups"][0])
        second["id"] = "second"
        for group, ids in ((first, ["p0", "p1"]), (second, ["p2", "p3"])):
            group["member_ids"] = ids
            group["spine"] = [edge for edge in group["spine"] if edge["source"] in ids and edge["target"] in ids]
            group["member_support"] = [r for r in group["member_support"] if r["paper_id"] in ids]
        proposal["groups"] = [first, second]
        for node in proposal["nodes"]: node["group_ids"] = ["table" if node["id"] in first["member_ids"] else "second"]
        bridge = proposal["edges"].pop(1)
        snapshot = build_snapshot(proposal, papers, None, "p0", "scope", 1)
        self.assertTrue(all(q["status"] == "evidence_linked" for q in snapshot["synthesis_quality"]["group_diagnostics"]))
        self.assertFalse(_explanation_complete(snapshot, set(papers)))
        proposal["edges"].append(bridge)
        connected = build_snapshot(proposal, papers, None, "p0", "scope", 1)
        self.assertTrue(_explanation_complete(connected, set(papers)))

    def test_incomplete_refinement_returns_real_gaps_to_next_exploration(self):
        provider = OmittingProvider(0)
        result = self.run_engine(provider, max_iterations=2, max_model_calls=20)
        self.assertEqual(result["status"], "completed")
        payloads = [json.loads(p.split("\nDATA:\n", 1)[1]) for p, _ in provider.calls]
        discoveries = [p for p in payloads if "unread_candidates" in p]
        self.assertEqual(len(discoveries), 2)
        self.assertTrue(discoveries[1]["evidence_tasks"])
        self.assertEqual([s["iteration"] for s in result["snapshots"]], [2])
        self.assertTrue({"p0", "p1", "p2"}.issubset({n["id"] for n in result["latest_snapshot"]["nodes"]}))

    def test_later_failure_preserves_last_complete_iteration(self):
        result = self.run_engine(OmittingProvider(99, fail_round=2), max_iterations=2, max_model_calls=4)
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertEqual(len(result["snapshots"]), 1)
        first = self.store.snapshot(result["id"], result["snapshots"][0]["id"])
        self.assertEqual(first, result["latest_snapshot"])
        self.assertEqual(first["completion_status"], "complete")


if __name__ == "__main__": unittest.main()
