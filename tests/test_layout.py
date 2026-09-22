import json
import subprocess
import unittest
from pathlib import Path

LAYOUT = Path(__file__).parents[1] / "src" / "deepanalyze" / "static" / "layout.js"

def run_plan(snapshot, groups=None, layout=None):
    payload = json.dumps({"snapshot": snapshot, "groups": groups, "layout": layout})
    script = f"const x=require({json.dumps(str(LAYOUT))}); process.stdout.write(JSON.stringify(x.plan({payload}.snapshot,{payload}.groups,{payload}.layout)));"
    return json.loads(subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True).stdout)

class LayoutTests(unittest.TestCase):
    def test_same_year_supported_dependency_is_ordered_subrows(self):
        snapshot = {"groups": [{"id": "g"}], "nodes": [{"id": "a", "year": 2020, "group_ids": ["g"]}, {"id": "b", "year": 2020, "group_ids": ["g"]}], "edges": [{"source": "a", "target": "b", "kind": "builds_on", "status": "supported"}]}
        self.assertEqual(run_plan(snapshot)["rows"][0]["cells"]["g"], [["a"], ["b"]])

    def test_forked_dependencies_share_level_subrow(self):
        snapshot = {"groups": [{"id": "g"}], "nodes": [{"id": x, "year": 2020, "group_ids": ["g"]} for x in ("a", "b", "c")], "edges": [{"source": "a", "target": x, "kind": "addresses", "status": "supported"} for x in ("b", "c")]}
        self.assertEqual(run_plan(snapshot)["rows"][0]["cells"]["g"], [["a"], ["b", "c"]])

    def test_three_independent_same_year_papers_share_a_row(self):
        nodes = [{"id": str(i), "year": 2020, "group_ids": ["g"]} for i in range(3)]
        result = run_plan({"groups": [{"id": "g"}], "nodes": nodes, "edges": []})
        self.assertEqual(result["rows"][0]["cells"]["g"], [["0", "1", "2"]])
        self.assertEqual(result["groups"][0]["columns"], 3)

    def test_four_independent_papers_wrap_without_losing_nodes(self):
        nodes = [{"id": str(i), "year": 2020, "group_ids": ["g"]} for i in range(4)]
        self.assertEqual(run_plan({"groups": [{"id": "g"}], "nodes": nodes, "edges": []})["rows"][0]["cells"]["g"], [["0", "1", "2"], ["3"]])

    def test_available_width_allocates_extra_columns_to_busiest_group(self):
        nodes = [{"id": f"a{i}", "year": 2020, "group_ids": ["a"]} for i in range(4)] + [{"id": "b0", "year": 2020, "group_ids": ["b"]}]
        result = run_plan({"groups": [{"id": "a"}, {"id": "b"}], "nodes": nodes, "edges": []}, None, 850)
        self.assertEqual(result["rows"][0]["cells"]["a"], [["a0", "a1", "a2"], ["a3"]])
        self.assertEqual(result["groups"][0]["columns"], 3)
        self.assertEqual(result["groups"][1]["columns"], 1)
        self.assertLessEqual(sum(group["width"] for group in result["groups"]), 850)

    def test_responsive_wrap_keeps_supported_dependency_levels_ordered(self):
        nodes = [{"id": x, "year": 2020, "group_ids": ["g"]} for x in ("a", "b", "c", "d")]
        edges = [{"source": "a", "target": x, "kind": "addresses", "status": "supported"} for x in ("b", "c", "d")]
        result = run_plan({"groups": [{"id": "g"}], "nodes": nodes, "edges": edges}, None, {"availableWidth": 420})
        self.assertEqual(result["rows"][0]["cells"]["g"], [["a"], ["b", "c"], ["d"]])
        self.assertEqual(result["groups"][0]["columns"], 2)
    def test_same_year_nonrejected_links_stagger_independent_peers(self):
        snapshot = {"groups": [{"id": "g"}], "nodes": [{"id": x, "year": 2020, "group_ids": ["g"]} for x in ("a", "b", "c")], "edges": [{"source": "a", "target": "c", "kind": "challenges", "status": "hypothesis"}]}
        self.assertEqual(run_plan(snapshot)["rows"][0]["cells"]["g"], [["a", "b"], ["c"]])

    def test_parallel_cards_have_real_offsets_without_new_years(self):
        snapshot = {"groups": [{"id": "g"}], "nodes": [{"id": str(i), "year": 2020, "group_ids": ["g"]} for i in range(3)], "edges": []}
        result = run_plan(snapshot)
        self.assertEqual(set(result["offsets"].values()), {0, 28, 56})
        self.assertEqual(result["years"], [2020])

    def test_geometry_routes_around_intervening_card_and_spreads_ports(self):
        script = "const x=require(" + json.dumps(str(LAYOUT)) + ");" + r"""
const a={id:'a',left:100,right:300,top:20,bottom:140};
const block={id:'block',left:100,right:300,top:180,bottom:300};
const b={id:'b',left:100,right:300,top:360,bottom:480};
const rectangles=[a,block,b];
const first=x.routeEdge(a,b,rectangles,{width:450,height:520,sourceSlot:0,sourceCount:2});
const second=x.routeEdge(a,b,rectangles,{width:450,height:520,sourceSlot:1,sourceCount:2});
const hits=first.points.slice(1).some((p,i)=>x.segmentHits(first.points[i],p,block,0));
process.stdout.write(JSON.stringify({collisions:first.collisions,hits,first:first.points,second:second.points,path:first.path}));
"""
        result = json.loads(subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True).stdout)
        self.assertEqual(result["collisions"], 0)
        self.assertFalse(result["hits"])
        self.assertNotEqual(result["first"][0], result["second"][0])
        self.assertIn("C ", result["path"])
        self.assertNotIn("L ", result["path"])
        self.assertTrue(20 <= result["first"][0][1] <= 140)
        self.assertTrue(360 <= result["first"][-1][1] <= 480)

    def test_multiple_blocks_and_unknown_year_last(self):
        edges = [{"source": "a", "target": "b", "kind": "addresses", "status": "hypothesis"}]
        snapshot = {"groups": [{"id": "g1"}, {"id": "g2"}], "nodes": [{"id": "a", "year": 2022, "group_ids": ["g1", "g2"]}, {"id": "b", "year": None, "group_ids": ["g2"]}], "edges": edges}
        result = run_plan(snapshot)
        self.assertEqual(result["years"], [2022, None])
        self.assertEqual(result["rows"][0]["cells"]["g1"], [["a"]])
        self.assertEqual(result["rows"][1]["cells"]["g2"], [["b"]])

    def test_plan_does_not_mutate_snapshot_inside_node(self):
        script = f"const x=require({json.dumps(str(LAYOUT))}); const s={{groups:[{{id:'g'}}],nodes:[{{id:'a',year:2020,group_ids:['g']}}],edges:[]}}; const before=JSON.stringify(s); x.plan(s); process.stdout.write(String(before===JSON.stringify(s)));"
        self.assertEqual(subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True).stdout, "true")