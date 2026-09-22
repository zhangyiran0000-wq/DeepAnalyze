import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

from deepanalyze.engine import ResearchEngine, _mainline_ids
from deepanalyze.schemas import normalize_config
from deepanalyze.store import RunStore
from tests.test_engine import FakeLiterature, FakeProvider


def linked(paper, anchor, direction):
    result = copy.deepcopy(paper)
    result["citation_links"] = [{"anchor_id": anchor,
        "direction": "cites_anchor" if direction == "citations" else "cited_by_anchor",
        "source_url": f"https://api.semanticscholar.org/graph/v1/paper/{anchor}/{direction}?limit=30"}]
    result["external_ids"] = {"s2": paper["id"]}
    return result


class CitationLibrary(FakeLiterature):
    def __init__(self, neighbors):
        super().__init__()
        self.neighbors, self.routes = neighbors, []
        for key, paper in self.papers.items():
            paper["external_ids"] = {"s2": key}

    def related(self, paper, limit=10, *, direction="both", offset=0):
        self.routes.append((paper["id"], direction, offset, limit))
        ids = self.neighbors.get((paper["id"], direction), [])
        return [linked(self.papers[key], paper["id"], direction) for key in ids[offset:offset + limit]]

    def search(self, *args, **kwargs):
        raise AssertionError("Unconnected keyword discovery must never run.")


class NoEdges(FakeProvider):
    def generate(self, prompt, **kwargs):
        result = super().generate(prompt, **kwargs)
        if "edges" in result["data"]:
            payload = result["data"]
            payload["edges"] = []
            for group in payload["groups"]: group["spine"] = []
            nodes = sorted(payload["nodes"], key=lambda n: n["id"])
            if nodes:
                first = nodes[0]
                payload["comparisons"] = [{"source": first["id"], "target": node["id"],
                    "relation": "alternative", "group_action": "merge", "shared_problem": "The same bounded correction case.",
                    "evidence_ids": [first["evidence"][0]["id"], node["evidence"][0]["id"]]} for node in nodes[1:]]
        return result


class CitationScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = RunStore(Path(self.temp.name))

    def run_engine(self, library, provider=None, **config):
        provider = provider or FakeProvider()
        run = self.store.create("seed", {"max_iterations": 2, "read_per_round": 3, **config})
        ResearchEngine(provider, library, self.store).run(run["id"], threading.Event())
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "completed", result.get("stop_reason"))
        return result, provider

    def test_anchor_component_excludes_related_hypotheses_and_isolated_nodes(self):
        nodes = [{"id": key} for key in ("seed", "older", "later", "challenge", "topic", "maybe", "isolated")]
        def edge(a, b, kind="addresses", status="supported"):
            return dict(source=a, target=b, kind=kind, status=status, problem="Specific problem",
                        mechanism="Concrete response", evidence_ids=[a, b])
        snapshot = {"nodes": nodes, "edges": [edge("older", "seed"), edge("seed", "later"),
                    edge("later", "challenge", "challenges"), edge("later", "topic", "related"),
                    edge("later", "maybe", status="hypothesis")]}
        self.assertEqual(set(_mainline_ids("seed", snapshot)), {"seed", "older", "later", "challenge"})
        snapshot["edges"][1]["status"] = "rejected"
        self.assertEqual(set(_mainline_ids("seed", snapshot)), {"seed", "older"})

    def test_both_directions_allow_needed_predecessor_and_preserve_provenance(self):
        lib = CitationLibrary({("p0", "citations"): ["p1"], ("p0", "references"): ["p2"]})
        lib.papers["p2"].update(year=2019, date="2019-01-01")
        result, provider = self.run_engine(lib, max_iterations=1)
        nodes = {n["id"]: n for n in result["latest_snapshot"]["nodes"]}
        self.assertEqual(set(nodes), {"p0", "p1", "p2"})
        self.assertEqual(nodes["p1"]["citation_links"][0]["direction"], "cites_anchor")
        self.assertEqual(nodes["p2"]["citation_links"][0]["direction"], "cited_by_anchor")
        self.assertEqual(nodes["p0"]["external_ids"], {"s2": "p0"})
        self.assertEqual({r[1] for r in lib.routes}, {"citations", "references"})
        for prompt, _ in provider.calls:
            data = json.loads(prompt.split("\nDATA:\n", 1)[1])
            if "unread_candidates" in data or ("source_packets" in data and "revision_feedback" not in data and "current_structure" not in data):
                self.assertEqual(data["discovery_mode"], "mainline_citations")
            self.assertNotIn("scope_keywords", data)

    def test_only_integrated_paper_opens_next_neighborhood(self):
        lib = CitationLibrary({("p0", "citations"): ["p1", "p3"], ("p1", "citations"): ["p2"],
                               ("p3", "citations"): ["p4"]})
        class Partial(FakeProvider):
            def generate(self, prompt, **kwargs):
                result = super().generate(prompt, **kwargs)
                if "edges" in result["data"]:
                    result["data"]["edges"] = [e for e in result["data"]["edges"]
                                               if "p3" not in {e["source"], e["target"]}]
                    payload = result["data"]
                    allowed = {(e["source"], e["target"]) for e in payload["edges"]}
                    for group in payload["groups"]:
                        group["spine"] = [step for step in group["spine"] if (step["source"], step["target"]) in allowed]
                    nodes = {n["id"]: n for n in payload["nodes"]}
                    if "p3" in nodes:
                        payload["comparisons"] = [{"source": "p0", "target": "p3", "relation": "alternative",
                            "group_action": "merge", "shared_problem": "A parallel bounded correction case.",
                            "evidence_ids": [nodes[k]["evidence"][0]["id"] for k in ("p0", "p3")]}]
                return result
        result, _ = self.run_engine(lib, Partial())
        anchors = {r[0] for r in lib.routes}
        self.assertIn("p1", anchors)
        self.assertNotIn("p3", anchors)
        self.assertNotIn("p4", lib.read_counts)
        self.assertIn("p2", lib.read_counts)
        self.assertNotIn("p3", result["latest_snapshot"]["mainline_ids"])

    def test_cache_without_current_mainline_provenance_cannot_refill_pool(self):
        lib = CitationLibrary({})
        cached = {"p2": lib.papers["p2"], "p3": linked(lib.papers["p3"], "p2", "citations")}
        run = self.store.create("seed", {"max_iterations": 1})
        self.store.working(run["id"], {"papers": cached})
        ResearchEngine(FakeProvider(), lib, self.store).run(run["id"], threading.Event())
        self.assertEqual(set(lib.read_counts), {"p0"})
        self.assertEqual(self.store.get(run["id"])["progress"]["candidates"], 1)

    def test_wrong_anchor_wrong_direction_and_search_url_do_not_qualify(self):
        class Invalid(CitationLibrary):
            def related(self, paper, **kwargs):
                wrong_anchor = linked(self.papers["p1"], "unrelated", kwargs["direction"])
                wrong_url = linked(self.papers["p2"], paper["id"], kwargs["direction"])
                wrong_url["citation_links"][0]["source_url"] = "https://api.semanticscholar.org/graph/v1/paper/search"
                wrong_direction = linked(self.papers["p3"], paper["id"], kwargs["direction"])
                wrong_direction["citation_links"][0]["direction"] = "cited_by_anchor" if kwargs["direction"] == "citations" else "cites_anchor"
                return [wrong_anchor, wrong_url, wrong_direction]
        lib = Invalid({})
        self.run_engine(lib, max_iterations=1)
        self.assertEqual(set(lib.read_counts), {"p0"})

    def test_cursors_continue_on_snapshot_branch_without_rewriting_history(self):
        lib = CitationLibrary({("p0", "citations"): ["p1", "p2", "p3", "p4"]})
        result, _ = self.run_engine(lib, NoEdges(), candidates_per_round=2, read_per_round=2)
        snapshot = result["latest_snapshot"]
        self.assertEqual(snapshot["discovery"]["cursors"]["p0"]["citations"], 2)
        self.assertEqual(snapshot["mainline_ids"], ["p0"])
        before = copy.deepcopy(snapshot)
        branch = self.store.resume(result["id"], snapshot["id"], {"max_iterations": 1, "candidates_per_round": 2})
        newlib = CitationLibrary(lib.neighbors)
        ResearchEngine(NoEdges(), newlib, self.store).run(branch["id"], threading.Event())
        self.assertIn(("p0", "citations", 2, 1), newlib.routes)
        self.assertEqual(self.store.snapshot(result["id"], snapshot["id"]), before)
        self.assertEqual(self.store.get(branch["id"])["status"], "completed")

    def test_domain_only_is_skipped_but_different_story_reaches_synthesis(self):
        lib = CitationLibrary({("p0", "citations"): ["p1", "p2"]})
        class RationaleProvider(FakeProvider):
            def generate(self, prompt, **kwargs):
                result = super().generate(prompt, **kwargs)
                if "selected_ids" in result["data"]:
                    result["data"]["candidate_rationales"] = [dict(paper_id=key, anchor_id="p0",
                        current_claim="A bounded update resolves one inconsistency.", different_story="The same update introduces a new ambiguity.",
                        selection_reason="Tests a consequence of the stated update." if key == "p1" else "Only shares a broad application label.",
                        problem_relation="mechanism_consequence" if key == "p1" else "shared_domain_only")
                        for key in ("p1", "p2")]
                return result
        result, provider = self.run_engine(lib, RationaleProvider(), max_iterations=1)
        self.assertIn("p1", lib.read_counts)
        self.assertNotIn("p2", lib.read_counts)
        payloads = [json.loads(p.split("\nDATA:\n", 1)[1]) for p, _ in provider.calls]
        data = next(d for d in payloads if "candidate_rationales" in d)
        self.assertTrue(any(r["different_story"] for r in data["candidate_rationales"] if r["paper_id"] == "p1"))
        self.assertEqual(len(result["latest_snapshot"]["discovery"]["candidate_rationales"]), 2)

    def test_snapshot_branch_restores_unread_frontier_before_advancing_pages(self):
        lib = CitationLibrary({("p0", "citations"): ["p1", "p2", "p3", "p4"]})
        result, _ = self.run_engine(lib, NoEdges(), max_iterations=1, candidates_per_round=4, read_per_round=1)
        snapshot = result["latest_snapshot"]
        self.assertEqual({p["id"] for p in snapshot["discovery"]["pending_candidates"]}, {"p1", "p2"})
        branch = self.store.resume(result["id"], snapshot["id"], {"max_iterations": 1, "candidates_per_round": 8})
        newlib = CitationLibrary(lib.neighbors)
        ResearchEngine(NoEdges(), newlib, self.store).run(branch["id"], threading.Event())
        self.assertTrue({"p1", "p2", "p3", "p4"}.issubset(newlib.read_counts))
        self.assertEqual(self.store.get(branch["id"])["status"], "completed")

    def test_external_id_alias_cannot_create_a_second_seed_node(self):
        class Aliases(CitationLibrary):
            def related(self, paper, **kwargs):
                alias = linked(self.papers["p0"], paper["id"], kwargs["direction"])
                alias["id"] = "alternate_seed_id"
                return [alias]
        lib = Aliases({})
        result, _ = self.run_engine(lib, max_iterations=1)
        self.assertEqual(set(lib.read_counts), {"p0"})
        self.assertEqual([n["id"] for n in result["latest_snapshot"]["nodes"]], ["p0"])

    def test_available_connection_to_one_anchor_overrides_domain_only_overlap_to_another(self):
        lib = CitationLibrary({("p0", "citations"): ["p1"]})
        class Mixed(FakeProvider):
            def generate(self, prompt, **kwargs):
                result = super().generate(prompt, **kwargs)
                if "selected_ids" in result["data"]:
                    result["data"]["candidate_rationales"] = [dict(paper_id="p1", anchor_id="p0",
                        current_claim="A provisional claim", different_story="An alternative interpretation",
                        selection_reason="Different aspect of the anchor", problem_relation=kind)
                        for kind in ("shared_domain_only", "uncertain")]
                return result
        self.run_engine(lib, Mixed(), max_iterations=1)
        self.assertIn("p1", lib.read_counts)

    def test_legacy_keywords_are_accepted_but_not_copied_to_new_config(self):
        self.assertNotIn("scope_keywords", normalize_config({"scope_keywords": ["Old field"]}))
        self.assertNotIn("scope_keywords", normalize_config())

    def test_comparison_context_prioritizes_the_actual_citation_anchor(self):
        lib = CitationLibrary({})
        new = linked(lib.read(lib.papers["p5"]), "p1", "citations")
        previous = {"iteration": 1, "nodes": [dict(p, problem="Shared broad topic") for p in list(lib.papers.values())[:5]]}
        related = ResearchEngine._relevant_papers(previous, lib.papers, [new], [])
        self.assertEqual(related[0]["id"], "p1")
        packets = ResearchEngine._source_packets([new], related, previous)
        pairs = ResearchEngine._comparison_pairs(previous, packets)
        self.assertIn({"source": "p1", "target": "p5"}, pairs)


if __name__ == "__main__":
    unittest.main()
