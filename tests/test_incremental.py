import copy
import unittest

from deepanalyze.engine import _account_sources
from deepanalyze.graph import build_snapshot, validate_edges


class IncrementalGraphTests(unittest.TestCase):
    def base(self):
        papers = {key: {"id": key, "title": key, "year": 2020+i,
            "date": f"{2020+i}-01-01", "source_status": "fulltext", "passages": [
            {"text": f"Source {key} describes a bounded correction operation.", "location": "Method"}]}
            for i, key in enumerate(("a", "b"))}
        proposal = {"groups": [{"id": "g", "label": "Corrections", "member_ids": ["a", "b"]}],
            "nodes": [{"id": key, "group_ids": ["g"], "evidence": [{"id": key+"_ev",
                "quote": p["passages"][0]["text"]}]} for key, p in papers.items()],
            "comparisons": [{"source": "a", "target": "b", "relation": "progression",
                "group_action": "merge", "evidence_ids": ["a_ev", "b_ev"]}],
            "edges": [{"source": "a", "target": "b", "kind": "addresses", "status": "supported",
                "problem": "Missing correction", "mechanism": "Bounded correction update",
                "evidence_ids": ["a_ev", "b_ev"], "historical_influence": "unknown"}]}
        return papers, build_snapshot(proposal, papers, None, "a", "scope", 1)

    def test_incremental_keeps_unchanged_judgments_and_history(self):
        papers, old = self.base()
        frozen = copy.deepcopy(old)
        proposal = {"update_mode": "incremental", "groups": old["groups"], "nodes": [], "edges": [], "comparisons": []}
        current = build_snapshot(proposal, papers, old, "a", "scope", 2)
        self.assertEqual(old, frozen)
        self.assertEqual(current["comparisons"], old["comparisons"])
        self.assertEqual(current["edges"], old["edges"])
        self.assertEqual(current["metrics"]["depth"], 1)
        self.assertEqual(current["edges"][0]["historical_influence"], "unknown")

    def test_explicit_retraction_supersedes_stored_comparison_and_edge(self):
        papers, old = self.base()
        update = {**old["edges"][0], "status": "rejected", "rationale": "Later evidence retracts this interpretation."}
        comparison = {**old["comparisons"][0], "relation": "alternative", "group_action": "merge"}
        proposal = {"update_mode": "incremental", "groups": old["groups"], "nodes": [],
            "edges": [update], "comparisons": [comparison]}
        current = build_snapshot(proposal, papers, old, "a", "scope", 2)
        self.assertEqual(len(current["edges"]), 1)
        self.assertEqual(current["edges"][0]["status"], "rejected")
        self.assertEqual(current["metrics"]["depth"], 0)
        self.assertEqual(len(current["comparisons"]), 1)
        self.assertEqual(current["comparisons"][0]["relation"], "alternative")
        self.assertEqual(old["metrics"]["depth"], 1)

    def test_missing_evidence_does_not_upgrade_on_incremental_reuse(self):
        papers, old = self.base()
        proposal = {"update_mode": "incremental", "groups": old["groups"], "nodes": [],
            "edges": [{**old["edges"][0], "status": "supported", "evidence_ids": []}]}
        current = build_snapshot(proposal, papers, old, "a", "scope", 2)
        self.assertEqual(current["edges"][0]["status"], "hypothesis")
        self.assertEqual(current["metrics"]["depth"], 0)

    def test_retained_date_warning_is_stable_and_rejection_stays_rejected(self):
        papers, old = self.base()
        for node in old["nodes"]:
            node["date"] = ""
        edges, _, _ = validate_edges(old["nodes"], old["edges"])
        again, _, _ = validate_edges(old["nodes"], edges)
        self.assertEqual(edges, again)
        old["nodes"][0]["year"] = None
        rejected, _, _ = validate_edges(old["nodes"], [{**edges[0], "status": "rejected"}])
        self.assertEqual(rejected[0]["status"], "rejected")

    def test_each_read_source_keeps_a_reviewable_disposition(self):
        sources = [{"id": key, "title": key, "year": 2020} for key in ("a", "b", "c", "d")]
        snapshot = {"nodes": [sources[0]]}
        proposal = {"dispositions": [
            {"paper_id": "a", "status": "included", "reason": "Grounded contribution"},
            {"paper_id": "b", "status": "included", "reason": "Claimed included but no node"},
            {"paper_id": "c", "status": "deferred", "reason": "Need the method section"}]}
        _account_sources(snapshot, proposal, sources, None)
        records = {r["paper_id"]: r for r in snapshot["source_dispositions"]}
        self.assertEqual([records[k]["status"] for k in ("a", "b", "c", "d")],
            ["included", "pending", "deferred", "pending"])
        self.assertEqual(records["a"]["reason"], "Grounded contribution")
        self.assertEqual(records["c"]["reason"], "Need the method section")
        prior = copy.deepcopy(snapshot)
        snapshot["nodes"].append(sources[2])
        _account_sources(snapshot, {"dispositions": []}, [], prior)
        self.assertEqual(next(d for d in snapshot["source_dispositions"] if d["paper_id"] == "c")["status"], "included")
        self.assertEqual(prior["source_dispositions"][2]["status"], "deferred")


if __name__ == "__main__":
    unittest.main()
