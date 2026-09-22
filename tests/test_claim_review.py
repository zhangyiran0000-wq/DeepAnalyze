import copy
import unittest
from deepanalyze.claim_review import checks, apply_reviews, record_reviews
from deepanalyze.engine import ResearchEngine, _explanation_complete
from deepanalyze.graph import build_snapshot
from tests.test_engine import FakeProvider, FakeLiterature


class ClaimReviewTests(unittest.TestCase):
    def fixture(self):
        lib = FakeLiterature()
        papers = {k: lib.read(v) for k,v in list(lib.papers.items())[:3]}
        packets = ResearchEngine._source_packets(list(papers.values()), [], None)
        proposal = FakeProvider().generate(ResearchEngine._synthesis_prompt("scope", None, packets, {}))["data"]
        return build_snapshot(proposal, papers, None, "p0", "scope", 1), papers

    def test_exact_quotations_do_not_automatically_pass_semantic_review(self):
        snapshot, _ = self.fixture()
        self.assertTrue(_explanation_complete(snapshot, {"p0", "p1", "p2"}))
        reviewed = apply_reviews(snapshot, {})
        self.assertFalse(_explanation_complete(reviewed, {"p0", "p1", "p2"}))
        self.assertTrue(reviewed["synthesis_quality"]["pending_reviews"])

    def test_missing_review_is_insufficient_and_retains_an_actionable_gap(self):
        snapshot, _ = self.fixture()
        cache = {}
        record_reviews(checks(snapshot), {"reviews": []}, cache)
        reviewed = apply_reviews(snapshot, cache)
        self.assertTrue(all(e["status"] == "hypothesis" for e in reviewed["edges"]))
        self.assertFalse(_explanation_complete(reviewed, {"p0", "p1", "p2"}))
        self.assertTrue(reviewed["gaps"])

    def test_changed_source_context_invalidates_previous_approval(self):
        snapshot, _ = self.fixture()
        original = checks(snapshot)
        cache = {item["id"]: {"status": "supported", "reason": "Fixture review", "missing_evidence": ""} for item in original}
        self.assertTrue(_explanation_complete(apply_reviews(snapshot, cache), {"p0", "p1", "p2"}))
        extra = {"p1": [{"id": "p1:counter", "text": "The gain depends on an incomparable evaluation protocol."}]}
        current = apply_reviews(snapshot, cache, extra)
        self.assertFalse(_explanation_complete(current, {"p0", "p1", "p2"}))
        self.assertTrue(current["synthesis_quality"]["pending_reviews"])
        self.assertEqual(snapshot["edges"][0]["status"], "supported")

    def test_local_context_omits_remote_paper_text(self):
        from deepanalyze.synthesis_loop import context_view
        snapshot, _ = self.fixture()
        view = context_view(snapshot, ["p0", "p1"])
        self.assertEqual({n["id"] for n in view["nodes"]}, {"p0", "p1"})
        self.assertTrue(all({e["source"],e["target"]} <= {"p0","p1"} for e in view["edges"]))

    def test_observation_basis_cannot_claim_experimental_support_with_foreign_quote(self):
        snapshot, papers = self.fixture()
        proposal = {"nodes": [{**snapshot["nodes"][0], "research_observations": [
            {"kind": "demonstrated_gain", "statement": "Higher reported score.", "basis": "reported_experiment",
             "evidence_ids": [snapshot["nodes"][1]["evidence"][0]["id"]]}]}], "groups": snapshot["groups"], "edges": []}
        value = build_snapshot(proposal, papers, snapshot, "p0", "scope", 2)
        observation = value["nodes"][0]["research_observations"][0]
        self.assertEqual(observation["basis"], "unknown")
        self.assertEqual(observation["evidence_ids"], [])


if __name__ == "__main__":
    unittest.main()
