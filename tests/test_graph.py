import copy
import unittest

from deepanalyze.graph import build_snapshot, validate_edges


def node(name, published="2020-01-01"):
    return {"id": name, "date": published, "year": 2020,
            "evidence": [{"id": name + "_ev", "verified": True}]}


def edge(source, target, kind="addresses", status="supported"):
    return {"source": source, "target": target, "kind": kind, "status": status,
            "problem": "A specific missing capability", "mechanism": "A specific state update",
            "evidence_ids": [source + "_ev", target + "_ev"]}


class GraphTests(unittest.TestCase):
    def test_cycle_rejected_and_nonprogress_links_do_not_inflate_depth(self):
        nodes = [node("a"), node("b"), node("c")]
        edges, gaps, metrics = validate_edges(nodes, [edge("a", "b"), edge("b", "c"), edge("c", "a"), edge("a", "c", "related")])
        self.assertEqual(edges[2]["status"], "rejected")
        self.assertEqual(metrics["depth"], 2)
        self.assertTrue(gaps)

    def test_backward_link_rejected_unknown_date_hypothesis(self):
        nodes = [node("a", "2021-01-01"), node("b", "2020-01-01"), {**node("c", ""), "year": None}]
        edges, _, metrics = validate_edges(nodes, [edge("a", "b"), edge("b", "c")])
        self.assertEqual([item["status"] for item in edges], ["rejected", "hypothesis"])
        self.assertEqual(metrics["depth"], 0)

    def test_year_only_dates_do_not_invent_order_within_year(self):
        nodes = [node("a", "2020-12-01"), node("b", "")]
        edges, _, metrics = validate_edges(nodes, [edge("a", "b")])
        self.assertEqual(edges[0]["status"], "supported")
        self.assertEqual(metrics["depth"], 1)

    def test_both_endpoints_need_verified_evidence(self):
        nodes = [node("a"), node("b")]
        nodes[1]["evidence"][0]["verified"] = False
        edges, gaps, metrics = validate_edges(nodes, [edge("a", "b")])
        self.assertEqual(edges[0]["status"], "hypothesis")
        self.assertEqual(metrics["depth"], 0)
        self.assertTrue(gaps)

    def test_identity_and_quote_grounding_override_model_metadata(self):
        papers = {name: {"id": name, "title": "Verified " + name, "year": 2020, "date": "2020-01-01", "url": "https://example.org/" + name,
                         "source_status": "fulltext", "passages": [{"id": name + "_passage", "text": "The source describes bounded records with a fixed table.", "location": "Section 2"}]}
                  for name in ("a", "b")}
        proposal = {"nodes": [
            {"id": "a", "title": "Invented title", "year": 1900, "evidence": [{"id": "a_ev", "quote": "The source describes bounded records with a fixed table."}]},
            {"id": "b", "evidence": [{"id": "b_ev", "quote": "A made up quotation unsupported by any supplied source."}]},
            {"id": "invented", "evidence": []}],
            "edges": [edge("a", "b")], "groups": [], "gaps": [], "review_notes": []}
        snapshot = build_snapshot(proposal, papers, None, "a", "scope", 1)
        self.assertEqual(len(snapshot["nodes"]), 2)
        self.assertEqual(snapshot["nodes"][0]["title"], "Verified a")
        self.assertEqual(snapshot["nodes"][0]["year"], 2020)
        self.assertEqual(snapshot["nodes"][1]["evidence"], [])
        self.assertEqual(snapshot["edges"][0]["status"], "hypothesis")
        self.assertEqual(snapshot["metrics"]["depth"], 0)

    def test_merge_reassigns_unchanged_nodes_and_removes_absorbed_lane(self):
        from deepanalyze.demo import demo_snapshot
        old = demo_snapshot(2)
        frozen = copy.deepcopy(old)
        retained = old["groups"][0]
        proposal = {"groups": [{"id": retained["id"], "label": retained["label"],
            "description": "Shared bounded-state problem", "common_problem": "Retaining corrections in bounded memory",
            "member_ids": [n["id"] for n in old["nodes"]],
            "merge_from": [g["id"] for g in old["groups"]]}], "nodes": [], "edges": []}
        new = build_snapshot(proposal, {}, old, old["seed_id"], old["scope"], 3)
        self.assertEqual(old, frozen)
        self.assertEqual(len(new["groups"]), 1)
        self.assertEqual(new["groups"][0]["color"], retained["color"])
        self.assertTrue(all(n["group_ids"] == [retained["id"]] for n in new["nodes"]))
        self.assertTrue(any(c["kind"] == "removed" and c["target_id"] in {g["id"] for g in old["groups"][1:]} for c in new["changes"]))

    def test_unapplied_grounded_merge_requires_consolidation(self):
        papers = {key: {"id": key, "title": key, "year": 2020, "passages": [
            {"text": "This source describes a shared bounded update problem.", "location": "Abstract"}]}
            for key in ("a", "b")}
        proposal = {"groups": [{"id": key, "label": key, "member_ids": [key]} for key in papers],
            "nodes": [{"id": key, "group_ids": [key], "evidence": [{"id": key + "_ev",
                "quote": papers[key]["passages"][0]["text"]}]} for key in papers],
            "comparisons": [{"source": "a", "target": "b", "group_action": "merge", "relation": "alternative",
                "evidence_ids": ["a_ev", "b_ev"]}], "edges": []}
        result = build_snapshot(proposal, papers, None, "a", "scope", 1)
        self.assertEqual(result["synthesis_quality"]["unresolved_merges"], 1)
        self.assertTrue(result["synthesis_quality"]["needs_consolidation"])
        proposal["comparisons"][0].update(relation="progression", group_action="keep_separate")
        result = build_snapshot(proposal, papers, None, "a", "scope", 1)
        self.assertEqual(result["synthesis_quality"]["split_progressions"], 1)
        self.assertTrue(result["synthesis_quality"]["needs_consolidation"])
        proposal["comparisons"][0]["evidence_ids"] = ["a_ev"]
        result = build_snapshot(proposal, papers, None, "a", "scope", 1)
        self.assertFalse(result["comparisons"][0]["grounded"])
        self.assertEqual(result["comparisons"][0]["group_action"], "uncertain")

    def test_independent_singletons_with_reasons_are_not_forced_to_merge(self):
        papers = {key: {"id": key, "title": key, "year": 2020} for key in ("a", "b", "c")}
        proposal = {"groups": [{"id": key, "label": key, "member_ids": [key],
                     "separation_reason": "Distinct bottleneck requiring different evidence."} for key in papers],
                    "nodes": [{"id": key, "group_ids": [key]} for key in papers], "edges": []}
        result = build_snapshot(proposal, papers, None, "a", "scope", 1)
        self.assertEqual(len(result["groups"]), 3)
        self.assertEqual(result["synthesis_quality"]["status"], "incomplete")
        self.assertTrue(result["synthesis_quality"]["needs_consolidation"])

    def test_group_identity_and_color_persist_and_retraction_is_recorded(self):
        from deepanalyze.demo import demo_snapshot
        old = demo_snapshot(2)
        frozen = copy.deepcopy(old)
        new = demo_snapshot(3, old)
        self.assertEqual(old, frozen)
        self.assertEqual([(g["id"], g["color"], g["label"]) for g in old["groups"]],
                         [(g["id"], g["color"], g["label"]) for g in new["groups"]])
        changed = [item for item in new["edges"] if item["source"] == "window" and item["target"] == "correction"]
        self.assertEqual(changed[0]["status"], "rejected")
        self.assertGreater(new["metrics"]["depth"], old["metrics"]["depth"])


    def test_reused_local_quote_names_resolve_within_the_member_paper(self):
        from deepanalyze.graph import stable_id, normalized
        quotes = {"a": "Earlier bounded storage loses a correction after a replacement.",
                  "b": "Later bounded storage retains a correction using a revised update."}
        papers = {key: {"id": key, "title": key, "year": 2020 + index,
                       "passages": [{"text": quote, "location": "Method"}]}
                  for index, (key, quote) in enumerate(quotes.items())}
        canonical = {key: stable_id("ev", key, normalized(quote)) for key, quote in quotes.items()}
        group = {"id": "g", "label": "Bounded correction", "core_concept": "Bounded correction",
            "label_nouns": ["correction"], "explanatory_claim": {"constraint": "Fixed storage", "mechanism": "Revise update", "consequence": "Retain correction"},
            "member_ids": ["a", "b"], "spine": [{"source": "a", "target": "b", "claim_connection": "Retain the previous missing correction"}],
            "member_support": [{"paper_id": key, "claim_connection": "Tests the same correction mechanism", "evidence_ids": ["quote1"]} for key in papers]}
        proposal = {"groups": [group], "nodes": [{"id": key, "group_ids": ["g"], "evidence": [{"id": "quote1", "quote": quote}]} for key,quote in quotes.items()],
            "edges": [{"source": "a", "target": "b", "kind": "addresses", "status": "supported", "problem": "Correction loss", "mechanism": "Revise retained update",
                       "evidence_ids": list(canonical.values())}]}
        result = build_snapshot(proposal, papers, None, "a", "scope", 1)
        support = {r["paper_id"]: r["evidence_ids"] for r in result["groups"][0]["member_support"]}
        self.assertEqual(support, {key: [value] for key,value in canonical.items()})
        self.assertEqual(result["groups"][0]["explanation_quality"]["status"], "evidence_linked")
        proposal["edges"][0]["evidence_ids"] = ["quote1"]
        ambiguous = build_snapshot(proposal, papers, None, "a", "scope", 1)
        self.assertNotEqual(ambiguous["edges"][0]["status"], "supported")

if __name__ == "__main__":
    unittest.main()
