"""Controlled checks of attribution and explanatory-spine boundaries, without models."""

import copy
import unittest

from deepanalyze.synthesis_quality import evaluate_groups


def node(key, group="g"):
    return {"id": key, "group_ids": [group],
            "evidence": [{"id": key + "_ev", "verified": True}]}


def edge(source, target, kind="addresses", status="supported"):
    return {"source": source, "target": target, "kind": kind, "status": status,
            "problem": "A prior limitation", "mechanism": "A specific mechanism change",
            "evidence_ids": [source + "_ev", target + "_ev"]}


def comparison(source, target, relation="alternative"):
    return {"source": source, "target": target, "relation": relation, "grounded": True,
            "shared_problem": "Updating bounded state",
            "evidence_ids": [source + "_ev", target + "_ev"]}


def group(members, pairs=(), key="g"):
    return {"id": key, "label": "A proposed line", "core_concept": "Retaining information in bounded state",
            "label_nouns": ["state", "updates"],
            "explanatory_claim": {"constraint": "State capacity is bounded",
                                  "mechanism": "Updates control which contributions persist",
                                  "consequence": "Changing the update changes retained information"},
            "spine": [{"source": source, "target": target,
                       "claim_connection": "This transition changes what the shared state retains"}
                      for source, target in pairs],
            "member_support": [{"paper_id": paper, "claim_connection": "This source supports the stated update mechanism",
                                "evidence_ids": [paper + "_ev"]} for paper in members]}


class SynthesisQualityTests(unittest.TestCase):
    def assess(self, members, pairs, *, proposal=None, edges=None, comparisons=None, nodes=None):
        return evaluate_groups([proposal or group(members, pairs)],
                               nodes or [node(key) for key in members],
                               edges if edges is not None else [edge(a, b) for a, b in pairs],
                               comparisons or [])[0]

    def test_evidence_linked_fork_does_not_require_single_path(self):
        members, pairs = ["a", "b", "c", "d"], [("a", "b"), ("a", "c"), ("b", "d")]
        result = self.assess(members, pairs)
        self.assertEqual(result["status"], "evidence_linked")
        self.assertEqual(result["spine_depth"], 2)
        self.assertEqual(result["covered_member_ids"], members)
        self.assertEqual(result["issues"], [])

    def test_topic_enumeration_and_pair_quotes_do_not_establish_a_spine(self):
        proposal = {"id": "g", "label": "Planning, supervision, prediction and risk",
                    "common_problem": "Improve autonomous driving"}
        result = self.assess(["a", "b"], [], proposal=proposal,
                             comparisons=[comparison("a", "b", "complementary")])
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["unexplained_member_ids"], ["a", "b"])
        self.assertIn("incomplete_explanatory_claim", result["issues"])
        self.assertIn("missing_spine", result["issues"])

    def test_at_most_five_declared_title_nouns_independent_of_core_target(self):
        for nouns, valid in [(["state"], True), (["one", "two", "three", "four", "five"], True),
                             (["one", "two", "three", "four", "five", "six"], False),
                             (["\u8bb0\u5fc6\u72b6\u6001", "state"], True)]:
            with self.subTest(nouns=nouns):
                proposal = group(["a", "b"], [("a", "b")])
                proposal["label_nouns"] = nouns
                result = self.assess(["a", "b"], [("a", "b")], proposal=proposal)
                self.assertEqual(result["status"] == "evidence_linked", valid)
                if not valid:
                    self.assertIn("label_noun_limit_exceeded", result["issues"])

    def test_missing_invalid_and_duplicate_title_nouns_remain_incomplete(self):
        for nouns, issue in [(None, "missing_label_nouns"), ([], "missing_label_nouns"),
                             ([""], "invalid_label_nouns"), ([None], "invalid_label_nouns"),
                             (["state", " State "], "duplicate_label_nouns")]:
            with self.subTest(nouns=nouns):
                proposal = group(["a", "b"], [("a", "b")])
                proposal["label_nouns"] = nouns
                result = self.assess(["a", "b"], [("a", "b")], proposal=proposal)
                self.assertEqual(result["status"], "incomplete")
                self.assertIn(issue, result["issues"])

    def test_core_target_requires_one_nonempty_phrase_not_legacy_concepts(self):
        for concept in (None, "", "   ", ["state"], 7):
            with self.subTest(concept=concept):
                proposal = group(["a", "b"], [("a", "b")])
                proposal["core_concept"] = concept
                proposal["core_concepts"] = ["state"]
                result = self.assess(["a", "b"], [("a", "b")], proposal=proposal)
                self.assertEqual(result["status"], "incomplete")
                self.assertIn("missing_core_concept", result["issues"])

    def test_explicit_core_objective_lists_do_not_pass_with_one_title_noun(self):
        for concept in ("retention, retrieval", "retention; retrieval", "retention\nretrieval",
                        "\u8bb0\u5fc6\u4fdd\u7559\u3001\u68c0\u7d22", "\u8bb0\u5fc6\u4fdd\u7559\uff0c\u68c0\u7d22",
                        "\u8bb0\u5fc6\u4fdd\u7559\uff1b\u68c0\u7d22",
                        "speed, balance between memory and accuracy",
                        "\u8ba1\u7b97\u3001\u5b58\u50a8\u4e4b\u95f4\u7684\u6743\u8861\u3001\u53ef\u89e3\u91ca\u6027"):
            with self.subTest(concept=concept):
                proposal = group(["a", "b"], [("a", "b")])
                proposal["core_concept"] = concept
                proposal["label_nouns"] = ["state"]
                result = self.assess(["a", "b"], [("a", "b")], proposal=proposal)
                self.assertEqual(result["status"], "incomplete")
                self.assertIn("multiple_core_targets", result["issues"])

    def test_relations_and_compound_phrases_do_not_imply_multiple_targets(self):
        for concept in ("Memory updates and state retention", "Trade-off between latency, memory, and accuracy",
                        "\u8ba1\u7b97\u3001\u5b58\u50a8\u4e4b\u95f4\u7684\u6743\u8861",
                        "Retention of attributes (features, confidence)",
                        "\u4fe1\u606f\u4fdd\u7559\uff08\u7279\u5f81\u3001\u7f6e\u4fe1\u5ea6\uff09",
                        "Retaining information across 1,000 updates"):
            with self.subTest(concept=concept):
                proposal = group(["a", "b"], [("a", "b")])
                proposal["core_concept"] = concept
                result = self.assess(["a", "b"], [("a", "b")], proposal=proposal)
                self.assertEqual(result["status"], "evidence_linked")

    def test_member_support_cannot_borrow_another_papers_evidence(self):
        proposal = group(["a", "b"], [("a", "b")])
        proposal["member_support"][1]["evidence_ids"] = ["a_ev"]
        result = self.assess(["a", "b"], [("a", "b")], proposal=proposal)
        self.assertIn("invalid_member_evidence", result["issues"])
        self.assertEqual(result["covered_member_ids"], ["a"])
        self.assertEqual(result["unexplained_member_ids"], ["b"])

    def test_mixed_own_and_foreign_evidence_does_not_pass(self):
        proposal = group(["a", "b"], [("a", "b")])
        proposal["member_support"][1]["evidence_ids"] = ["a_ev", "b_ev"]
        self.assertIn("invalid_member_evidence", self.assess(["a", "b"], [("a", "b")], proposal=proposal)["issues"])

    def test_complementary_branch_cannot_inflate_explained_coverage(self):
        result = self.assess(["a", "b", "c"], [("a", "b")],
                             comparisons=[comparison("b", "c", "complementary")])
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["covered_member_ids"], ["a", "b"])
        self.assertEqual(result["unexplained_member_ids"], ["c"])

    def test_alternative_and_challenge_attach_without_inflating_spine_depth(self):
        result = self.assess(["a", "b", "c", "d"], [("a", "b")],
                             edges=[edge("a", "b"), edge("b", "d", "challenges")],
                             comparisons=[comparison("b", "c")])
        self.assertEqual(result["status"], "evidence_linked")
        self.assertEqual(result["spine_depth"], 1)
        self.assertEqual(result["unexplained_member_ids"], [])

    def test_parallel_alternatives_can_explain_members_at_real_depth_zero(self):
        result = self.assess(["a", "b", "c"], [],
                             comparisons=[comparison("a", "b"), comparison("a", "c")])
        self.assertEqual(result["status"], "evidence_linked")
        self.assertEqual(result["spine_depth"], 0)
        self.assertEqual(result["covered_member_ids"], ["a", "b", "c"])
        self.assertEqual(result["issues"], [])

    def test_parallel_anchor_uses_earliest_member_not_input_order_or_identity(self):
        nodes = [{**node("a"), "year": 2025}, {**node("b"), "year": 2020},
                 {**node("c"), "year": 2024}]
        result = self.assess(["a", "b", "c"], [], nodes=nodes,
                             comparisons=[comparison("b", "a"), comparison("b", "c")])
        self.assertEqual(result["status"], "evidence_linked")
        self.assertEqual(result["spine_depth"], 0)

    def test_parallel_alternatives_can_connect_in_multiple_layers_but_complementary_cannot(self):
        result = self.assess(["a", "b", "c"], [], comparisons=[comparison("a", "b"), comparison("b", "c")])
        self.assertEqual(result["status"], "evidence_linked")
        self.assertEqual(result["covered_member_ids"], ["a", "b", "c"])
        complementary = self.assess(["a", "b", "c"], [], comparisons=[comparison("a", "b"), comparison("a", "c", "complementary")])
        self.assertEqual(complementary["status"], "incomplete")
        self.assertEqual(complementary["unexplained_member_ids"], ["c"])

    def test_parallel_root_and_members_still_need_personal_claim_support(self):
        proposal = group(["a", "b"])
        proposal["member_support"][1]["evidence_ids"] = ["a_ev"]
        result = self.assess(["a", "b"], [], proposal=proposal,
                             comparisons=[comparison("a", "b")])
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["unexplained_member_ids"], ["b"])

    def test_supported_challenge_can_ground_a_parallel_branch(self):
        result = self.assess(["a", "b"], [], edges=[edge("a", "b", "challenges")])
        self.assertEqual(result["status"], "evidence_linked")
        self.assertEqual(result["spine_depth"], 0)

    def test_grounded_alternative_can_supply_missing_spine_but_invalid_spine_remains_incomplete(self):
        proposal = group(["a", "b"])
        proposal["spine"] = None
        result = self.assess(["a", "b"], [], proposal=proposal, comparisons=[comparison("a", "b")])
        self.assertEqual(result["status"], "evidence_linked")
        proposal["spine"] = [{"source": "a", "target": "b", "claim_connection": "unvalidated"}]
        result = self.assess(["a", "b"], [], proposal=proposal, comparisons=[comparison("a", "b")])
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("invalid_spine_transition", result["issues"])

    def test_alternative_transitive_closure_can_explain_multiple_layers_without_depth_gain(self):
        result = self.assess(["a", "b", "c", "d"], [("a", "b")], comparisons=[comparison("b", "c"), comparison("c", "d")])
        self.assertEqual(result["status"], "evidence_linked")
        self.assertEqual(result["covered_member_ids"], ["a", "b", "c", "d"])
        self.assertEqual(result["spine_depth"], 1)

    def test_grounded_label_alone_cannot_attach_a_branch(self):
        fake = comparison("b", "c")
        fake["evidence_ids"] = ["b_ev"]
        result = self.assess(["a", "b", "c"], [("a", "b")], comparisons=[fake])
        self.assertEqual(result["unexplained_member_ids"], ["c"])

    def test_disconnected_subspines_do_not_establish_one_explanation(self):
        result = self.assess(["a", "b", "c", "d"], [("a", "b"), ("c", "d")])
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("disconnected_spine", result["issues"])
        self.assertEqual(result["spine_depth"], 1)
        self.assertEqual(result["covered_member_ids"], ["a", "b"])

    def test_hypothesis_rejected_or_unattributed_edge_cannot_form_spine(self):
        invalid_edges = [edge("a", "b", status="hypothesis"), edge("a", "b", status="rejected"),
                         {**edge("a", "b"), "evidence_ids": ["a_ev"]}]
        for invalid in invalid_edges:
            with self.subTest(edge=invalid):
                result = self.assess(["a", "b"], [("a", "b")], edges=[invalid])
                self.assertIn("invalid_spine_transition", result["issues"])
                self.assertEqual(result["spine_depth"], 0)
                self.assertEqual(result["status"], "incomplete")

    def test_duplicate_steps_do_not_increase_depth_and_cycles_are_incomplete(self):
        result = self.assess(["a", "b"], [("a", "b"), ("a", "b")])
        self.assertEqual(result["spine_depth"], 1)
        self.assertEqual(result["status"], "evidence_linked")
        cycle = self.assess(["a", "b"], [("a", "b"), ("b", "a")])
        self.assertIn("cyclic_spine", cycle["issues"])
        self.assertEqual(cycle["spine_depth"], 0)

    def test_singleton_among_other_sources_cannot_claim_a_complete_line(self):
        result = self.assess(["a"], [], nodes=[node("a"), node("b", "other")])
        self.assertEqual(result["status"], "evidence_linked")
        self.assertEqual(result["covered_member_ids"], ["a"])
        self.assertIn("singleton_group", result["warnings"])
        self.assertNotIn("missing_spine", result["issues"])

    def test_one_source_bootstrap_is_complete_only_with_its_own_evidence(self):
        result = self.assess(["a"], [])
        self.assertEqual(result["status"], "evidence_linked")
        self.assertEqual(result["spine_depth"], 0)
        self.assertEqual(result["covered_member_ids"], ["a"])
        self.assertEqual(result["issues"], [])
        proposal = group(["a"])
        proposal["member_support"][0]["evidence_ids"] = []
        incomplete = self.assess(["a"], [], proposal=proposal)
        self.assertEqual(incomplete["status"], "incomplete")
        self.assertEqual(incomplete["unexplained_member_ids"], ["a"])

    def test_one_source_with_several_groups_is_not_the_bootstrap_base_case(self):
        source = node("a")
        source["group_ids"] = ["g", "h"]
        results = evaluate_groups([group(["a"]), group(["a"], key="h")], [source], [], [])
        self.assertTrue(all(item["status"] == "evidence_linked" for item in results))
        self.assertTrue(all("singleton_group" in item["warnings"] for item in results))

    def test_declared_nonmembers_cannot_be_covered(self):
        proposal = group(["a", "b", "foreign"], [("a", "b")])
        result = self.assess(["a", "b"], [("a", "b")], proposal=proposal,
                             nodes=[node("a"), node("b"), node("foreign", "other")])
        self.assertIn("invalid_member_support", result["issues"])
        self.assertEqual(result["covered_member_ids"], ["a", "b"])

    def test_unverified_evidence_cannot_support_member_or_transition(self):
        nodes = [node("a"), node("b")]
        nodes[1]["evidence"][0]["verified"] = False
        result = self.assess(["a", "b"], [("a", "b")], nodes=nodes)
        self.assertEqual(result["covered_member_ids"], [])
        self.assertIn("invalid_member_evidence", result["issues"])

    def test_legacy_groups_and_inputs_are_preserved_without_mutation(self):
        args = ([{"id": "g", "label": "Legacy group"}], [node("a"), node("b")], [edge("a", "b")], [])
        before = copy.deepcopy(args)
        result = evaluate_groups(*args)[0]
        self.assertEqual(args, before)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["unexplained_member_ids"], ["a", "b"])

    def test_ambiguous_evidence_identity_cannot_be_attributed(self):
        nodes = [node("a"), node("b")]
        nodes[1]["evidence"].append({"id": "a_ev", "verified": True})
        result = self.assess(["a", "b"], [("a", "b")], nodes=nodes)
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("invalid_member_evidence", result["issues"])


if __name__ == "__main__":
    unittest.main()
