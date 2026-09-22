import unittest

from deepanalyze.evidence_tasks import candidate_bridges, plan_evidence_tasks, targeted_packets


def paper(pid, title, passages):
    return {"id": pid, "title": title, "year": 2020, "passages": passages}


class EvidenceTaskTests(unittest.TestCase):
    def setUp(self):
        self.papers = {
            "seed": paper("seed", "Seed mechanism", [{"id": "s0", "location": "Abstract", "text": "shared mechanism"}]),
            "a": paper("a", "Unexplained bridge", [
                {"id": "a0", "location": "1", "text": "context before"},
                {"id": "a1", "location": "2", "text": "mechanism limitation bridge"},
                {"id": "a2", "location": "3", "text": "context after"}]),
            "b": paper("b", "Candidate bridge", [{"id": "b0", "location": "Abstract", "text": "mechanism bridge"}]),
        }

    def test_plan_keeps_singletons_as_merge_and_invalid_as_bridge(self):
        snap = {"seed_id": "seed", "nodes": [{"id": "seed"}, {"id": "a"}],
                "edges": [{"source": "seed", "target": "a", "status": "rejected", "rationale": "direction unclear"}],
                "gaps": [], "synthesis_quality": {"unconnected_source_ids": ["a"]}}
        tasks = plan_evidence_tasks(snap, self.papers, {"seed", "a"})
        self.assertTrue(any(t["kind"] == "bridge" and set(t["paper_ids"]) == {"seed", "a"} for t in tasks))
        self.assertTrue(any(t["kind"] == "merge" and t["paper_ids"] == ["a", "seed"] for t in tasks))

    def test_packets_include_adjacent_complete_passages_and_seen_is_deprioritized(self):
        task = {"paper_ids": ["a", "seed"], "question": "mechanism limitation", "terms": ["mechanism", "limitation"]}
        result = targeted_packets(self.papers, task, max_chars=1000, seen_passage_ids={"a1"})
        a = next(x for x in result if x["id"] == "a")
        self.assertEqual({p["id"] for p in a["passages"]}, {"a0", "a1", "a2"})
        self.assertFalse(a["is_new"])

    def test_bridge_candidates_are_limited_to_eligible_unread(self):
        task = {"question": "mechanism candidate", "terms": ["mechanism", "candidate"]}
        self.assertEqual(candidate_bridges(task, self.papers, {"seed"}, ["seed", "a", "b"], 1), ["b"])


    def test_packets_keep_both_endpoints_and_strict_budget(self):
        task = {"paper_ids": ["a", "b"], "question": "mechanism", "terms": ["mechanism"]}
        result = targeted_packets(self.papers, task, max_chars=35)
        self.assertEqual({p["id"] for p in result}, {"a", "b"})
        self.assertLessEqual(sum(len(x.get("text", "")) for q in result for x in q["passages"]), 35)

    def test_oversized_passage_is_source_gap(self):
        papers = {"x": paper("x", "Long", [{"id": "x0", "text": "z" * 100}])}
        result = targeted_packets(papers, {"paper_ids": ["x"], "terms": ["z"]}, max_chars=10)
        self.assertEqual(result[0]["passages"], [])
        self.assertIn("source_gap", result[0])

    def test_relevant_seen_passage_beats_unrelated_unseen(self):
        papers = {"x": paper("x", "X", [{"id": "old", "text": "mechanism mechanism"}, {"id": "new", "text": "unrelated"}])}
        result = targeted_packets(papers, {"paper_ids": ["x"], "terms": ["mechanism"]}, max_chars=30, seen_passage_ids={"old"})
        self.assertEqual(result[0]["passages"][0]["id"], "old")

    def test_singleton_without_relation_stays_source(self):
        snap = {"seed_id": "seed", "nodes": [{"id": "seed"}, {"id": "a"}], "edges": [], "groups": [], "gaps": [], "synthesis_quality": {"unconnected_source_ids": ["a"]}}
        tasks = plan_evidence_tasks(snap, self.papers, {"seed", "a"})
        task = next(t for t in tasks if "a" in t["paper_ids"])
        self.assertEqual(task["kind"], "source")
        self.assertEqual(task["paper_ids"], ["a"])
    def test_survey_covers_sections_with_complete_passages(self):
        from deepanalyze.evidence_tasks import survey_packets
        papers = {"x": paper("x", "Survey", [
            {"id": "ab", "location": "Abstract", "text": "abstract claim"},
            {"id": "me", "location": "Methods", "text": "our method and model"},
            {"id": "ev", "location": "Evaluation", "text": "benchmark baseline ablation protocol"},
            {"id": "li", "location": "Limitations", "text": "limitation and future work"},
            {"id": "rw", "location": "Related Work", "text": "prior work"}])}
        result = survey_packets(papers, 1000)
        packet = result[0]
        self.assertEqual({p["id"] for p in packet["passages"]}, {"ab", "me", "ev", "li", "rw"})
        self.assertFalse(packet["source_gap"] if "source_gap" in packet else False)

    def test_survey_budget_is_strict_and_reports_missing_sections(self):
        from deepanalyze.evidence_tasks import survey_packets
        papers = {"x": paper("x", "Survey", [{"id": "ab", "location": "Abstract", "text": "a" * 20}, {"id": "ev", "location": "Evaluation", "text": "b" * 20}]),
                  "y": paper("y", "Other", [{"id": "yy", "location": "Abstract", "text": "c" * 20}])}
        result = survey_packets(papers, 30)
        total = sum(len(p.get("text", "")) for q in result for p in q["passages"])
        self.assertLessEqual(total, 30)
        self.assertTrue(any("source_gap" in q for q in result))
    def test_invalid_group_spine_pair_gets_precise_bridge_task(self):
        from deepanalyze.evidence_tasks import plan_evidence_tasks
        snap = {"nodes": [{"id": "a"}, {"id": "b"}], "edges": [], "comparisons": [], "gaps": [],
                "groups": [{"id": "g", "spine": [{"source": "a", "target": "b", "claim_connection": "changes the update rule"}]}]}
        tasks = plan_evidence_tasks(snap, self.papers, {"a", "b"})
        task = next(t for t in tasks if t["kind"] == "bridge" and set(t["paper_ids"]) == {"a", "b"})
        self.assertIn("a -> b", task["question"])
        self.assertIn("changes the update rule", task["question"])

if __name__ == "__main__":
    unittest.main()
