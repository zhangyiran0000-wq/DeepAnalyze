import copy
import unittest

from deepanalyze.reanalysis import reanalyze_sources


class ReanalysisBatchTests(unittest.TestCase):
    def test_batches_assess_then_structure_and_preserve_corpus(self):
        papers = {f"p{i}": {"id": f"p{i}", "title": f"Paper {i}", "year": 2020 + i,
            "passages": [{"id": f"p{i}_passage", "text": f"Paper {i} reports a measured bounded result in evaluation.", "location": "Results"}]} for i in range(15)}
        previous = {"seed_id": "p0", "scope": "bounded question", "groups": [{"id": "stale"}],
            "edges": [{"id": "stale_edge"}], "comparisons": [{"id": "stale_comparison"}], "gaps": [{"id": "stale_gap"}],
            "nodes": [{"id": "p0", "problem": "old problem", "mechanism": "old mechanism", "evidence": [], "group_ids": []}]}
        frozen = copy.deepcopy(previous)
        calls = []
        checkpoints = []

        def generate(role, prompt, schema):
            calls.append((role, prompt, schema))
            if role == "paper_assessment":
                import json
                payload = json.loads(prompt.split("DATA:\n", 1)[1])
                return {"assessments": [{"id": pid, "mechanism": "bounded update",
                    "research_assessment": {"outcome": "demonstrated", "claimed_problem": "The bounded question",
                        "demonstrated_result": "A measured result", "conditions": "On the supplied evaluation", "unresolved": "Generalization", "evidence_ids": [pid + "_ev"]},
                    "evidence": [{"id": pid + "_ev", "quote": f"Paper {pid[1:]} reports a measured bounded result in evaluation."}]} for pid in payload["paper_ids"]]}
            return {"update_mode": "incremental", "dispositions": [], "scope": "bounded question", "groups": [], "comparisons": [], "edges": [], "gaps": [], "review_notes": []}

        proposal, snapshot = reanalyze_sources(previous, papers, scope="bounded question", seed_id="p0", iteration=4, language="en",
            generate=generate, publish=lambda *args: None, save_checkpoint=checkpoints.append)
        self.assertEqual([role for role, _, _ in calls].count("paper_assessment"), 3)
        self.assertEqual([role for role, _, _ in calls].count("synthesis"), 1)
        self.assertTrue(all("nodes" not in schema["properties"] for role, _, schema in calls if role == "synthesis"))
        self.assertEqual(set(n["id"] for n in snapshot["nodes"]), set(papers))
        self.assertEqual(len(checkpoints), 3)
        self.assertEqual(previous, frozen)
        self.assertEqual(proposal["nodes"], [])
        self.assertNotIn("stale", {g["id"] for g in snapshot["groups"]})
        self.assertEqual(snapshot["edges"], [])

    def test_resume_skips_completed_batches_but_retries_missing_batch(self):
        papers = {f"p{i}": {"id": f"p{i}", "title": f"Paper {i}", "passages": [{"id": f"p{i}_x", "text": f"Paper {i} reports a measured bounded result in evaluation.", "location": "Results"}]} for i in range(10)}
        calls = []
        checkpoints = []

        def response(role, prompt, schema):
            calls.append(role)
            if role == "paper_assessment":
                import json
                payload = json.loads(prompt.split("DATA:\n", 1)[1])
                return {"assessments": [{"id": pid, "mechanism": "m", "research_assessment": {"outcome": "unknown", "claimed_problem": "question", "demonstrated_result": "", "conditions": "", "unresolved": "open", "evidence_ids": []}, "evidence": []} for pid in payload["paper_ids"]]}
            return {"update_mode": "incremental", "dispositions": [], "scope": "scope", "groups": [], "comparisons": [], "edges": [], "gaps": [], "review_notes": []}

        first_calls = {"n": 0}
        def interrupted(role, prompt, schema):
            if role == "paper_assessment":
                first_calls["n"] += 1
                if first_calls["n"] == 2:
                    raise RuntimeError("interrupted")
            return response(role, prompt, schema)

        with self.assertRaises(RuntimeError):
            reanalyze_sources({}, papers, scope="scope", seed_id="p0", iteration=1, language="en", generate=interrupted, publish=lambda *a: None, save_checkpoint=checkpoints.append)
        self.assertEqual(len(checkpoints), 1)
        resumed_calls = []
        def resumed(role, prompt, schema):
            resumed_calls.append(role)
            return response(role, prompt, schema)
        reanalyze_sources(checkpoints[-1], papers, scope="scope", seed_id="p0", iteration=2, language="en", generate=resumed, publish=lambda *a: None, save_checkpoint=lambda value: None)
        self.assertEqual(resumed_calls.count("paper_assessment"), 1)
        self.assertEqual(resumed_calls.count("synthesis"), 1)


if __name__ == "__main__":
    unittest.main()
