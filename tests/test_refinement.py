"""Controlled refinement tests; no model, network, or application service."""

import copy
import unittest

from deepanalyze.graph import build_snapshot
from deepanalyze.refinement import candidate_score, choose_candidate, local_patch_proposal


def _edge(source, target, review="supported"):
    result = {"source": source, "target": target, "kind": "addresses", "status": "supported",
              "problem": "The previous representation retains stale contributions.",
              "mechanism": "The next update removes obsolete contributions.",
              "evidence_ids": [source + "_ev", target + "_ev"]}
    if review is not None:
        result["semantic_review"] = {"status": review, "reason": "Checked both source claims."}
    return result


def _group(key, members, pairs, review="supported"):
    result = {"id": key, "label": "Retained state", "core_concept": "Updating retained state",
              "label_nouns": ["state"], "member_ids": list(members),
              "explanatory_claim": {"constraint": "State is bounded", "mechanism": "Correct stale state",
                                    "consequence": "Obsolete contributions can be removed"},
              "spine": [{"source": a, "target": b, "claim_connection": "Changes the update"} for a, b in pairs],
              "member_support": [{"paper_id": key, "claim_connection": "Shows the update behavior",
                                  "evidence_ids": [key + "_ev"]} for key in members]}
    if review is not None:
        result["semantic_review"] = {"status": review, "reason": "Checked the group claim."}
    return result


def _snapshot(members=("a", "b", "c"), pairs=(("a", "b"), ("b", "c")), review="supported"):
    return {"seed_id": members[0], "groups": [_group("g", members, pairs, review)],
            "nodes": [{"id": key, "title": key, "year": 2020 + index,
                       "date": f"{2020 + index}-01-01", "group_ids": ["g"],
                       "problem": "Bounded state", "mechanism": "A state update", "solves": "Removes stale state",
                       "evidence": [{"id": key + "_ev", "verified": True,
                                     "quote": "This source describes retained state updates for " + key + "."}]}
                      for index, key in enumerate(members)],
            "edges": [_edge(a, b, review) for a, b in pairs], "comparisons": [], "gaps": []}


class RefinementScoreTests(unittest.TestCase):
    def test_reviewed_chain_has_coverage_and_depth(self):
        self.assertEqual(candidate_score(_snapshot(), {"a", "b", "c"}), (3, 0, 2, 0, 0))

    def test_legacy_relations_have_structural_coverage_but_no_reviewed_depth(self):
        old, new = _snapshot(review=None), _snapshot()
        self.assertEqual(candidate_score(old, {"a", "b", "c"}), (3, 0, 0, 0, 0))
        best, decision = choose_candidate(old, new, {"a", "b", "c"})
        self.assertIs(best, new)
        self.assertTrue(decision["accepted"])

    def test_explicit_negative_review_does_not_support_coverage_or_depth(self):
        for status in ("insufficient", "contradicted"):
            with self.subTest(status=status):
                snapshot = _snapshot()
                snapshot["edges"][1]["semantic_review"]["status"] = status
                score = candidate_score(snapshot, {"a", "b", "c"})
                self.assertEqual(score[0], 2)
                self.assertEqual(score[2], 1)

    def test_unverified_group_claim_cannot_contribute_coverage(self):
        old, new = _snapshot(), _snapshot()
        new["groups"][0]["semantic_review"]["status"] = "insufficient"
        self.assertEqual(candidate_score(new, {"a", "b", "c"})[0], 0)
        self.assertFalse(choose_candidate(old, new, {"a", "b", "c"})[1]["accepted"])

    def test_reviewed_depth_requires_reviewed_group_claim(self):
        snapshot = _snapshot()
        snapshot["groups"][0].pop("semantic_review")
        self.assertEqual(candidate_score(snapshot, {"a", "b", "c"})[0], 3)
        self.assertEqual(candidate_score(snapshot, {"a", "b", "c"})[2], 0)

    def test_completion_blocking_format_repair_is_an_improvement(self):
        old, new = _snapshot(), _snapshot()
        old["groups"][0]["label_nouns"] = list("abcdef")
        self.assertTrue(choose_candidate(old, new, {"a", "b", "c"})[1]["accepted"])

    def test_metrics_and_stale_diagnostics_cannot_manufacture_improvement(self):
        old = _snapshot()
        new = copy.deepcopy(old)
        new["metrics"] = {"depth": 9000, "supported_edges": 9000}
        new["synthesis_quality"] = {"group_diagnostics": [{"covered_member_ids": ["unknown"]}]}
        best, decision = choose_candidate(old, new, {"a", "b", "c"})
        self.assertIs(best, old)
        self.assertFalse(decision["accepted"])
        self.assertEqual(decision["before"], decision["after"])

    def test_additional_redundant_edges_are_not_rewarded(self):
        old, new = _snapshot(), _snapshot()
        new["edges"].append(_edge("a", "c"))
        self.assertEqual(candidate_score(old, {"a", "b", "c"}), candidate_score(new, {"a", "b", "c"}))
        self.assertFalse(choose_candidate(old, new, {"a", "b", "c"})[1]["accepted"])

    def test_a_deeper_reviewed_chain_beats_a_wider_tree(self):
        old = _snapshot(pairs=(("a", "b"), ("a", "c")))
        self.assertTrue(choose_candidate(old, _snapshot(), {"a", "b", "c"})[1]["accepted"])

    def test_fewer_groups_preferred_at_equal_coverage_validity_and_depth(self):
        old = _snapshot(members=("a", "b", "c", "d"), pairs=(("a", "b"), ("b", "c"), ("b", "d")))
        new = copy.deepcopy(old)
        old["groups"] = [_group("g", ("a", "b", "c"), (("a", "b"), ("b", "c"))),
                         _group("h", ("b", "d"), (("b", "d"),))]
        old["nodes"][1]["group_ids"] = ["g", "h"]
        old["nodes"][3]["group_ids"] = ["h"]
        best, decision = choose_candidate(old, new, {"a", "b", "c", "d"})
        self.assertIs(best, new)
        self.assertTrue(decision["accepted"])

    def test_more_total_coverage_cannot_replace_a_previously_explained_member(self):
        old = _snapshot(members=("a", "b", "c", "d"), pairs=(("a", "b"), ("b", "c"), ("c", "d")))
        new = copy.deepcopy(old)
        old["groups"][0]["member_support"] = old["groups"][0]["member_support"][:2]
        new["groups"][0]["member_support"] = [r for r in new["groups"][0]["member_support"] if r["paper_id"] != "b"]
        required = {"a", "b", "c", "d"}
        self.assertGreater(candidate_score(new, required)[0], candidate_score(old, required)[0])
        best, decision = choose_candidate(old, new, required)
        self.assertIs(best, old)
        self.assertIn("previously explained", decision["reason"])

    def test_previously_retained_unexplained_nodes_cannot_be_dropped(self):
        old = _snapshot()
        old["nodes"].append({"id": "pending", "group_ids": [], "evidence": []})
        self.assertIn("removed", choose_candidate(old, _snapshot(), {"a", "b", "c", "pending"})[1]["reason"])

    def test_reviewed_coverage_cannot_revert_to_legacy_coverage(self):
        best, decision = choose_candidate(_snapshot(), _snapshot(review=None), {"a", "b", "c"})
        self.assertFalse(decision["accepted"])
        self.assertIn("reviewed source coverage", decision["reason"])

    def test_foreign_evidence_cannot_support_depth(self):
        snapshot = _snapshot()
        snapshot["edges"][1]["evidence_ids"] = ["a_ev", "b_ev"]
        score = candidate_score(snapshot, {"a", "b", "c"})
        self.assertEqual(score[0], 2)
        self.assertEqual(score[2], 1)

    def test_first_candidate_is_retained_without_prior_explanation(self):
        candidate = {"nodes": []}
        best, decision = choose_candidate(None, candidate, {"a"})
        self.assertIs(best, candidate)
        self.assertTrue(decision["accepted"])
        self.assertIn("initial", decision["reason"])

    def test_scoring_does_not_mutate_either_snapshot(self):
        old, new = _snapshot(), _snapshot(review=None)
        frozen = copy.deepcopy((old, new))
        choose_candidate(old, new, {"a", "b", "c"})
        self.assertEqual((old, new), frozen)

    def test_unknown_edge_kind_is_normalized_without_crashing(self):
        snapshot = _snapshot()
        snapshot["edges"].append({**_edge("a", "c"), "kind": "unexpected"})
        self.assertEqual(candidate_score(snapshot, {"a", "b", "c"})[2], 2)


class LocalPatchTests(unittest.TestCase):
    def test_local_node_patch_preserves_fields_and_ignores_remote_mutations(self):
        base = _snapshot()
        patch = local_patch_proposal({"nodes": [{"id": "a", "problem": "Overwrite remote"},
                                                {"id": "b", "results": "New measurement", "group_ids": ["other"]}]},
                                     base, {"b"})
        self.assertEqual([n["id"] for n in patch["nodes"]], ["b"])
        self.assertEqual(patch["nodes"][0]["problem"], base["nodes"][1]["problem"])
        self.assertEqual(patch["nodes"][0]["group_ids"], ["g"])
        self.assertEqual(patch["nodes"][0]["results"], "New measurement")
        self.assertEqual(patch["update_mode"], "incremental")

    def test_local_relations_require_focus_and_known_endpoints(self):
        links = [_edge("a", "c"), _edge("b", "c"), _edge("b", "intruder")]
        patch = local_patch_proposal({"edges": links, "comparisons": links}, _snapshot(), {"b"})
        for field in ("edges", "comparisons"):
            self.assertEqual([(e["source"], e["target"]) for e in patch[field]], [("b", "c")])

    def test_local_patch_freezes_group_claims_and_uses_actual_memberships(self):
        base = _snapshot()
        base["groups"][0].pop("member_ids")
        patch = local_patch_proposal({"groups": [_group("other", ("b",), ())]}, base, {"b"})
        self.assertEqual(patch["groups"][0]["id"], "g")
        self.assertEqual(patch["groups"][0]["member_ids"], ["a", "b", "c"])
        self.assertEqual(patch["groups"][0]["explanatory_claim"], base["groups"][0]["explanatory_claim"])

    def test_only_explicit_regroup_allows_membership_changes(self):
        proposal = {"groups": [_group("new", ("a", "b", "c"), (("a", "b"), ("b", "c")))],
                    "nodes": [{"id": "b", "group_ids": ["new"]}, {"id": "a", "problem": "Remote mutation"}]}
        patch = local_patch_proposal(proposal, _snapshot(), {"b"}, allow_regroup=True)
        self.assertEqual(patch["groups"], proposal["groups"])
        self.assertEqual(patch["nodes"][0]["group_ids"], ["new"])
        self.assertEqual([n["id"] for n in patch["nodes"]], ["b"])

    def test_unrelated_gaps_survive_local_replacement(self):
        base = _snapshot()
        base["gaps"] = [{"id": "remote", "paper_ids": ["a", "c"], "description": "Remote gap"},
                        {"id": "local", "paper_ids": ["b"], "description": "Old local gap"}]
        proposal = {"gaps": [{"id": "replacement", "paper_ids": ["b"], "description": "New local gap"},
                            {"id": "unasked", "paper_ids": ["a"], "description": "Remote change"}]}
        patch = local_patch_proposal(proposal, base, {"b"})
        self.assertEqual([g["id"] for g in patch["gaps"]], ["remote", "replacement"])

    def test_normalization_preserves_omitted_remote_nodes_edges_and_groups(self):
        base = _snapshot()
        papers = {n["id"]: {**n, "passages": [{"text": n["evidence"][0]["quote"], "location": "Method"}]}
                  for n in base["nodes"]}
        base = build_snapshot(base, papers, None, "a", "scope", 1)
        proposal = {"nodes": [{"id": "b", "results": "Updated local result"}], "groups": []}
        patch = local_patch_proposal(proposal, base, {"b"})
        result = build_snapshot(patch, papers, base, "a", "scope", 2)
        self.assertEqual({n["id"] for n in result["nodes"]}, {"a", "b", "c"})
        self.assertEqual(len(result["edges"]), 2)
        self.assertEqual([g["id"] for g in result["groups"]], ["g"])
        self.assertEqual(next(n for n in result["nodes"] if n["id"] == "a"), base["nodes"][0])

    def test_new_local_source_stays_unassigned_until_regroup(self):
        patch = local_patch_proposal({"nodes": [{"id": "d", "group_ids": ["g"]}]}, _snapshot(), {"d"})
        self.assertEqual(patch["nodes"][0]["group_ids"], [])
        self.assertNotIn("d", patch["groups"][0]["member_ids"])

    def test_patching_does_not_mutate_inputs(self):
        base = _snapshot()
        proposal = {"nodes": [{"id": "b", "mechanism": "Different update"}], "groups": []}
        before = copy.deepcopy((base, proposal))
        patch = local_patch_proposal(proposal, base, {"b"})
        patch["groups"][0]["label"] = "Changed returned copy"
        patch["nodes"][0]["evidence"].clear()
        self.assertEqual((base, proposal), before)


if __name__ == "__main__":
    unittest.main()
