import copy
import json
import unittest
from deepanalyze.claim_review import checks
from deepanalyze.engine import ResearchEngine, _Stop, _explanation_complete, _retain_required_sources
from deepanalyze.graph import build_snapshot
from deepanalyze.synthesis_loop import refine_snapshot
from tests.test_engine import FakeLiterature, FakeProvider


class SynthesisLoopTests(unittest.TestCase):
    def fixture(self):
        lib = FakeLiterature()
        papers = {k: lib.read(p) for k,p in list(lib.papers.items())[:3]}
        packets = ResearchEngine._source_packets(list(papers.values()), [], None)
        proposal = FakeProvider().generate(ResearchEngine._synthesis_prompt("scope", None, packets, {}))["data"]
        baseline = build_snapshot(proposal, papers, None, "p0", "scope", 1)
        cache = {item["id"]: {"status": "supported", "reason": "Fixture review", "missing_evidence": ""} for item in checks(baseline)}
        return papers, baseline, {"claim_reviews": cache}

    def run_loop(self, snapshot, papers, feedback, generate, baseline, **kwargs):
        attempts = []
        self.attempts = attempts
        return refine_snapshot(snapshot, papers, set(papers), scope="scope", seed_id="p0", iteration=1, language="zh",
            generate=generate, publish=lambda *a: None, checkpoint=lambda: None,
            save=lambda value,*a: attempts.append(copy.deepcopy(value)), read_source=lambda k: None,
            complete=kwargs.get("complete", _explanation_complete), retain=_retain_required_sources,
            can_advance=True, feedback=feedback, baseline=baseline)

    def test_interrupted_candidate_review_cannot_replace_accepted_best(self):
        papers, baseline, feedback = self.fixture()
        candidate = copy.deepcopy(baseline)
        candidate["edges"][0]["mechanism"] = "A different unreviewed mechanism."
        def budget(*args):
            raise _Stop("Synthetic budget limit")
        with self.assertRaises(_Stop):
            self.run_loop(candidate, papers, feedback, budget, baseline)
        best = feedback["best_snapshot"]
        self.assertEqual(best["edges"][0]["mechanism"], baseline["edges"][0]["mechanism"])
        self.assertTrue(any(v["synthesis_quality"].get("pending_reviews") for v in self.attempts))

    def test_new_round_proposal_cannot_regress_previous_coverage(self):
        papers, baseline, feedback = self.fixture()
        candidate = copy.deepcopy(baseline)
        candidate["nodes"][0]["solves"] = ""
        def approve(role, prompt, schema):
            data = json.loads(prompt.split("\nDATA:\n",1)[1])
            return {"reviews": [{"id": c["id"], "status": "supported", "reason": "Fixture", "missing_evidence": ""}
                                for c in data["relation_checks"]]}
        best, advance = self.run_loop(candidate, papers, feedback, approve, baseline)
        self.assertFalse(advance)
        self.assertEqual(best["nodes"][0]["solves"], baseline["nodes"][0]["solves"])
        self.assertFalse(feedback["decisions"][0]["accepted"])

    def test_successive_supported_merges_continue_after_first_improvement(self):
        papers, baseline, _ = self.fixture()
        template = copy.deepcopy(baseline["groups"][0])
        def partition(chunks):
            groups = []
            for i, ids in enumerate(chunks):
                group = copy.deepcopy(template)
                group["id"] = "partition_" + str(i)
                group["member_ids"] = ids
                group["member_support"] = [r for r in group["member_support"] if r["paper_id"] in ids]
                group["spine"] = [e for e in group["spine"] if e["source"] in ids and e["target"] in ids]
                groups.append(group)
            return groups
        baseline["groups"] = partition([["p0"], ["p1"], ["p2"]])
        for i, node in enumerate(baseline["nodes"]):
            node["group_ids"] = ["partition_" + str(i)]
        cache = {c["id"]: {"status": "supported", "reason": "Fixture", "missing_evidence": ""}
                 for c in checks(baseline)}
        merges = []
        def generate(role, prompt, schema):
            data = json.loads(prompt.split("\nDATA:\n", 1)[1])
            if role == "relation_review":
                return {"reviews": [{"id": c["id"], "status": "supported", "reason": "Fixture", "missing_evidence": ""}
                                    for c in data["relation_checks"]]}
            self.assertEqual(role, "regrouping")
            merges.append(role)
            chunks = [["p0", "p1"], ["p2"]] if len(merges) == 1 else [["p0", "p1", "p2"]]
            return {"groups": partition(chunks), "review_notes": []}
        best, advance = self.run_loop(baseline, papers, {"claim_reviews": cache}, generate, baseline)
        self.assertEqual(len(merges), 2)
        self.assertEqual(len(best["groups"]), 1)
        self.assertTrue(_explanation_complete(best, set(papers)))
        self.assertFalse(advance)

    def test_new_reading_invalidates_old_approval_before_interruptible_review(self):
        papers, baseline, feedback = self.fixture()
        baseline["gaps"] = [{"id": "gap", "paper_ids": ["p0","p1"], "description": "Check the experimental comparison conditions."}]
        papers["p1"]["passages"].append({"id": "counter", "text": "The experimental comparison conditions use a different benchmark protocol.",
                                        "location": "Experiments", "url": "https://example.org/p1"})
        def budget(*args):
            raise _Stop("Synthetic budget limit")
        with self.assertRaises(_Stop):
            self.run_loop(baseline, papers, feedback, budget, baseline, complete=lambda *a: False)
        best = feedback["best_snapshot"]
        self.assertTrue(best["synthesis_quality"]["pending_reviews"])
        self.assertFalse(_explanation_complete(best, set(papers)))
        self.assertTrue(any(p.get("id") == "counter" for p in feedback["review_context"]["p1"]))


if __name__ == "__main__":
    unittest.main()
