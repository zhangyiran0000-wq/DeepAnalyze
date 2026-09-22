import copy
import unittest
from tests.test_refinement import _snapshot, _edge
from deepanalyze.graph import stable_id
from deepanalyze.synthesis_quality import evaluate_groups, knowledge_metrics, stage_connections
from deepanalyze.refinement import candidate_score, choose_candidate
from deepanalyze.claim_review import checks, apply_reviews
from deepanalyze.engine import _explanation_complete, _mainline_ids


def knowledge_snapshot():
    value = _snapshot()
    group = value["groups"][0]
    group.update(explanation_model="knowledge_transitions_v1", root_id="a")
    group["spine"] = [{"source":"a", "target":"b", "claim_connection":"A bounded overwrite can erase relevant state.",
                       "before":"Discarding stale entries suffices.", "after":"Selective retention is also necessary.", "transition_type":"revision"}]
    value["edges"] = [{**_edge("a", "b"), "id":stable_id("edge","a","b","addresses")}]
    for node in value["nodes"]:
        node["research_assessment"] = {"outcome":"partial", "claimed_problem":"Stale state hurts retrieval.",
          "demonstrated_result":"The tested update improves bounded retrieval.", "conditions":"Controlled synthetic sequences.",
          "unresolved":"Generalization is untested.", "evidence_ids":[node["id"]+"_ev"]}
    for row in group["member_support"]:
        key=row["paper_id"]
        row.update(role="replication" if key=="c" else "revision", stage_anchor_id="b" if key=="c" else key,
                   knowledge_change="Repeats the finding." if key=="c" else "Revises the retention assumption.",
                   removal_effect="Loses an independent check." if key=="c" else "Loses the failure boundary.",
                   attachment_evidence_ids=["b_ev","c_ev"] if key=="c" else [])
    return value


class KnowledgeTransitionsTests(unittest.TestCase):
    def evaluate(self, value):
        return evaluate_groups(value["groups"],value["nodes"],value["edges"],value["comparisons"])[0]

    def test_replication_retained_without_inventing_a_progression(self):
        value=knowledge_snapshot()
        quality=self.evaluate(value)
        self.assertEqual(quality["status"],"evidence_linked")
        self.assertEqual(quality["covered_member_ids"],["a","b","c"])
        self.assertEqual(knowledge_metrics(value)["knowledge_depth"],1)
        self.assertEqual(candidate_score(value,{"a","b","c"})[:3],(3,0,1))
        self.assertEqual(stage_connections(value,True),[("c","b")])
        value["synthesis_quality"]={"group_diagnostics":[quality]}
        self.assertTrue(_explanation_complete(value,{"a","b","c"}))

    def test_extra_raw_paper_edges_do_not_raise_knowledge_depth(self):
        first=knowledge_snapshot(); second=copy.deepcopy(first)
        second["edges"].append(_edge("b","c"))
        self.assertEqual(candidate_score(first,{"a","b","c"}),candidate_score(second,{"a","b","c"}))
        self.assertEqual(knowledge_metrics(second)["knowledge_depth"],1)

    def test_replication_cannot_be_promoted_to_spine_for_depth(self):
        value=knowledge_snapshot()
        value["edges"].append(_edge("b","c"))
        value["groups"][0]["spine"].append({"source":"b","target":"c","claim_connection":"Same finding again",
              "before":"The old assumption fails.","after":"It fails in another test.","transition_type":"advance"})
        self.assertIn("incremental_work_on_spine",self.evaluate(value)["issues"])
        self.assertEqual(knowledge_metrics(value)["knowledge_depth"],0)

    def test_negative_result_can_be_a_reviewed_transition(self):
        value=knowledge_snapshot(); value["edges"][0]["kind"]="challenges"
        value["nodes"][1]["research_assessment"]["outcome"]="contradicted"
        self.assertEqual(self.evaluate(value)["status"],"evidence_linked")
        self.assertEqual(knowledge_metrics(value)["knowledge_depth"],1)

    def test_attachment_requires_both_sources_and_direct_stage_anchor(self):
        for anchor,refs in (("missing",["b_ev","c_ev"]),("b",["a_ev","c_ev"]),("c",["c_ev"])):
            value=knowledge_snapshot(); row=value["groups"][0]["member_support"][2]
            row.update(stage_anchor_id=anchor,attachment_evidence_ids=refs)
            with self.subTest(anchor=anchor,refs=refs):
                self.assertIn("invalid_stage_attachment",self.evaluate(value)["issues"])
                self.assertEqual(stage_connections(value,True),[])

    def test_outcome_without_own_evidence_does_not_pass(self):
        value=knowledge_snapshot()
        value["nodes"][1]["research_assessment"]["evidence_ids"]=["a_ev"]
        self.assertIn("missing_research_assessment",self.evaluate(value)["issues"])

    def test_no_change_cannot_manufacture_a_transition(self):
        value=knowledge_snapshot(); step=value["groups"][0]["spine"][0]
        step["after"]=step["before"]
        self.assertIn("missing_knowledge_transition",self.evaluate(value)["issues"])

    def test_unreviewed_or_rejected_group_cannot_inflate_depth(self):
        for status in (None,"insufficient","contradicted"):
            value=knowledge_snapshot()
            if status is None:value["groups"][0].pop("semantic_review")
            else:value["groups"][0]["semantic_review"]["status"]=status
            self.assertEqual(knowledge_metrics(value)["knowledge_depth"],0)

    def test_unreviewed_spine_cannot_validate_attachments(self):
        value=knowledge_snapshot()
        value["edges"][0].pop("semantic_review")
        self.assertEqual(knowledge_metrics(value)["knowledge_depth"],0)
        self.assertEqual(stage_connections(value,True),[])
        self.assertEqual(stage_connections(value,False),[("c","b")])
        self.assertEqual(_mainline_ids("a",value),["a"])
        self.assertEqual(_mainline_ids("a",knowledge_snapshot()),["a","b"])

    def test_outcomes_roles_and_transitions_invalidate_cached_review(self):
        original=knowledge_snapshot()
        fingerprint=next(c["id"] for c in checks(original) if c["kind"]=="group")
        for mutate in (lambda v:v["nodes"][1]["research_assessment"].update(outcome="demonstrated"),
                       lambda v:v["groups"][0]["member_support"][2].update(removal_effect="A different inference"),
                       lambda v:v["groups"][0]["spine"][0].update(after="Another boundary")):
            changed=copy.deepcopy(original);mutate(changed)
            self.assertNotEqual(fingerprint,next(c["id"] for c in checks(changed) if c["kind"]=="group"))

    def test_old_paper_count_depth_does_not_block_new_stage_account(self):
        old=_snapshot();new=knowledge_snapshot()
        best,decision=choose_candidate(old,new,{"a","b","c"})
        self.assertIs(best,new)
        self.assertTrue(decision["accepted"])

    def test_apply_reviews_publishes_knowledge_metric(self):
        value=knowledge_snapshot()
        reviews={item["id"]:{"status":"supported","reason":"Bounded evidence", "missing_evidence":""} for item in checks(value)}
        result=apply_reviews(value,reviews)
        self.assertEqual(result["metrics"]["knowledge_depth"],1)
        self.assertTrue(_explanation_complete(result,{"a","b","c"}))


if __name__=="__main__":unittest.main()
