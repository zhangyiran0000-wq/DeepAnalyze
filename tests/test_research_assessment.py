import copy
import unittest

from deepanalyze.graph import build_snapshot


class ResearchAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.papers = {
            key: {
                "id": key, "title": key, "year": 2020 + i,
                "date": f"{2020 + i}-01-01",
                "passages": [{"id": key + "_passage", "text": f"Fabricated source {key} reports a measured result.", "location": "Results"}],
            }
            for i, key in enumerate(("paper_a", "paper_b"))
        }

    def test_assessment_separates_claim_from_result_and_bounds_provenance(self):
        proposal = {
            "groups": [{"id": "g", "label": "Transition", "member_ids": ["paper_a", "paper_b"],
                "explanation_model": "knowledge_transitions_v1", "root_id": "paper_a",
                "spine": [{"source": "paper_a", "target": "paper_b", "claim_connection": "updates the method",
                           "before": "Earlier stated limitation", "after": "Later measured result", "transition_type": "revision"}],
                "member_support": [{"paper_id": "paper_a", "claim_connection": "Anchor", "evidence_ids": ["a_ev"],
                    "role": "advance", "stage_anchor_id": "paper_a", "knowledge_change": "Introduces a test", "removal_effect": "Removes the anchor"},
                    {"paper_id": "paper_b", "claim_connection": "Attached result", "evidence_ids": ["b_ev"],
                    "role": "revision", "stage_anchor_id": "paper_a", "knowledge_change": "Revises the result", "removal_effect": "Loses the revision",
                    "attachment_evidence_ids": ["a_ev", "b_ev"]}] }],
            "nodes": [
                {"id": "paper_a", "group_ids": ["g"], "evidence": [{"id": "a_ev", "quote": self.papers["paper_a"]["passages"][0]["text"]}],
                 "research_assessment": {"outcome": "demonstrated", "claimed_problem": "A claimed bottleneck",
                    "demonstrated_result": "A measured result", "conditions": "Only in a bounded setup", "unresolved": "External validity", "evidence_ids": ["a_ev"]}},
                {"id": "paper_b", "group_ids": ["g"], "evidence": [{"id": "b_ev", "quote": self.papers["paper_b"]["passages"][0]["text"]}],
                 "research_assessment": {"outcome": "demonstrated", "claimed_problem": "Another claim",
                    "demonstrated_result": "Unsupported assertion", "evidence_ids": ["a_ev"]}},
            ],
            "edges": [], "comparisons": [], "gaps": [], "review_notes": []
        }
        snapshot = build_snapshot(proposal, self.papers, None, "paper_a", "scope", 1)
        nodes = {n["id"]: n for n in snapshot["nodes"]}
        self.assertEqual(nodes["paper_a"]["research_assessment"]["outcome"], "demonstrated")
        self.assertEqual(nodes["paper_b"]["research_assessment"]["evidence_ids"], [])
        self.assertEqual(nodes["paper_b"]["research_assessment"]["outcome"], "unknown")
        group = snapshot["groups"][0]
        self.assertEqual(group["spine"][0]["before"], "Earlier stated limitation")
        self.assertEqual(group["spine"][0]["transition_type"], "revision")
        support = next(r for r in group["member_support"] if r["paper_id"] == "paper_b")
        self.assertEqual(len(support["attachment_evidence_ids"]), 2)
        self.assertTrue(all(ref in {ev["id"] for n in nodes.values() for ev in n["evidence"]} for ref in support["attachment_evidence_ids"]))

    def test_direct_source_passage_ids_bind_assessments_and_attachments(self):
        proposal={"groups":[{"id":"g","label":"Measured correction","member_ids":["paper_a","paper_b"], "explanation_model":"knowledge_transitions_v1",
          "root_id":"paper_a","spine":[],"member_support":[{"paper_id":"paper_b","claim_connection":"Same tested case",
          "evidence_ids":["paper_b_passage"],"stage_anchor_id":"paper_a","role":"replication","knowledge_change":"Repeated finding",
          "removal_effect":"Loses replication", "attachment_evidence_ids":["paper_a_passage","paper_b_passage"]}]}],
          "nodes":[{"id":"paper_a","group_ids":["g"],"evidence":[],"research_assessment":{"outcome":"demonstrated",
                    "claimed_problem":"Claim","demonstrated_result":"Result","conditions":"Condition","unresolved":"",
                    "evidence_ids":["paper_a_passage"]}},{"id":"paper_b","group_ids":["g"],"evidence":[]}],"edges":[]}
        result=build_snapshot(proposal,self.papers,None,"paper_a","scope",1)
        first=next(n for n in result["nodes"] if n["id"]=="paper_a")
        self.assertEqual(first["research_assessment"]["outcome"],"demonstrated")
        self.assertEqual(len(first["research_assessment"]["evidence_ids"]),1)
        self.assertEqual(len(result["groups"][0]["member_support"][0]["attachment_evidence_ids"]),2)

    def test_incremental_build_preserves_new_fields_and_legacy_stays_legacy(self):
        base = {"groups": [{"id": "g", "label": "Transition", "member_ids": ["paper_a"],
            "explanation_model": "knowledge_transitions_v1", "root_id": "paper_a", "spine": [], "member_support": []}],
            "nodes": [{"id": "paper_a", "group_ids": ["g"], "evidence": [],
                "research_assessment": {"outcome": "not_tested", "claimed_problem": "Claim", "demonstrated_result": "", "conditions": "", "unresolved": "Open", "evidence_ids": []}}], "edges": []}
        first = build_snapshot(base, self.papers, None, "paper_a", "scope", 1)
        update = {"update_mode": "incremental", "groups": first["groups"], "nodes": [], "edges": [], "comparisons": []}
        second = build_snapshot(update, self.papers, first, "paper_a", "scope", 2)
        self.assertEqual(second["nodes"][0]["research_assessment"], first["nodes"][0]["research_assessment"])
        legacy = build_snapshot({"groups": [{"id": "old", "label": "Old", "member_ids": ["paper_a"]}], "nodes": [{"id": "paper_a", "group_ids": ["old"]}], "edges": []}, self.papers, None, "paper_a", "scope", 1)
        self.assertNotIn("explanation_model", legacy["groups"][0])
        self.assertNotIn("research_assessment", legacy["nodes"][0])


if __name__ == "__main__":
    unittest.main()
