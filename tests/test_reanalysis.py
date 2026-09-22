import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from deepanalyze.store import RunStore
from deepanalyze.schemas import DEFAULT_CONFIG


class ReanalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=RunStore(Path(self.temp.name))
        self.original=self.store.create("Synthetic question",DEFAULT_CONFIG,"live")
        self.key=self.original["id"]
        self.store.update(self.key,status="budget_exhausted",progress={"model_calls":100,"elapsed_seconds":18000})
        self.cached={"papers":{key:{"id":key,"title":key,"abstract":"A sufficiently long synthetic technical finding.","passages":[]} for key in ("a","b","unread")},
                     "read_ids":["a","b"],"synthesis_draft":{"id":"draft","iteration":2,"seed_id":"a","nodes":[]},
                     "discovery":{"pending_candidates":[{"id":"unread"}]},"refinement":{"claim_reviews":{"old":"approval"}}}
        self.store.working(self.key,self.cached)
        self.config={**DEFAULT_CONFIG,"max_iterations":1,"max_model_calls":12,"max_seconds":600}

    def test_independent_budget_and_immutable_corpus_parent(self):
        before=copy.deepcopy(self.store.get(self.key));working=self.store.working(self.key)
        result=self.store.reanalyze(self.key,self.config)
        branch=self.store.working(result["id"])
        self.assertEqual(self.store.get(self.key),before)
        self.assertEqual(self.store.working(self.key),working)
        self.assertEqual(set(branch["papers"]),{"a","b"})
        self.assertEqual(branch["discovery"]["pending_candidates"],[])
        self.assertEqual(branch["refinement"],{})
        self.assertTrue(branch["fixed_corpus"])
        self.assertTrue(result["parent"]["reanalysis"])
        self.assertNotIn("budget_carry",result)
        self.assertEqual(self.store.synthesis_budget(result["id"])["remaining_model_calls"],12)
        self.assertEqual(self.store.synthesis_budget(result["id"])["iteration_limit"],2)
        with self.assertRaises(ValueError):self.store.retry_synthesis(self.key)

    def test_requires_config_and_finished_run(self):
        with self.assertRaises(ValueError):self.store.reanalyze(self.key,None)
        self.store.update(self.key,status="running")
        with self.assertRaises(ValueError):self.store.reanalyze(self.key,self.config)

    def test_rejects_missing_or_mismatched_read_source(self):
        for change in (lambda w:w["papers"].pop("b"), lambda w:w["papers"]["b"].update(id="other"),
                       lambda w:w["papers"]["b"].update(abstract="",passages=[])):
            cached=copy.deepcopy(self.cached);change(cached);self.store.working(self.key,cached)
            with self.assertRaises(ValueError):self.store.reanalyze(self.key,self.config)

    def test_engine_reuses_fixed_corpus_without_resolving_or_searching(self):
        from tests.test_engine import FakeLiterature, FakeProvider
        from deepanalyze.engine import ResearchEngine
        sources=FakeLiterature()
        papers={key:sources.read(sources.papers[key]) for key in ("p0","p1")}
        self.store.working(self.key,{"papers":papers,"read_ids":list(papers),
            "synthesis_draft":{"id":"saved","seed_id":"p0","iteration":1,"scope":"Synthetic table correction", "nodes":[],"groups":[],"edges":[]},
            "discovery":{"mode":"mainline_citations"}})
        branch=self.store.reanalyze(self.key,{**self.config,"max_iterations":10})
        class NoFetch:
            def __getattr__(self,name):
                raise AssertionError("Fixed-corpus run attempted a literature operation: "+name)
        class CachedProvider(FakeProvider):
            def generate(self,prompt,**kwargs):
                data=json.loads(prompt.split("\nDATA:\n",1)[1])
                if data.get("assessment_pass"):
                    self.calls.append((prompt,kwargs))
                    return {"data":{"assessments":[{"id":paper["id"],"mechanism":"Change the bounded table update.",
                        "research_assessment":{"outcome":"partial","claimed_problem":"Earlier retained tables omit corrections.",
                            "demonstrated_result":"A bounded correction case changes.","conditions":"Synthetic setting only.",
                            "unresolved":"Capacity limits.","evidence_ids":[paper["passages"][0]["id"]]},
                        "evidence":[{"id":paper["passages"][0]["id"],"quote":paper["passages"][0]["text"]}]}
                        for paper in data["survey_packets"]]},"usage":{}}
                return super().generate(prompt,**kwargs)
        provider=CachedProvider()
        ResearchEngine(provider,NoFetch(),self.store).run(branch["id"],threading.Event())
        result=self.store.get(branch["id"])
        self.assertEqual(result["status"],"completed")
        self.assertEqual({n["id"] for n in result["latest_snapshot"]["nodes"]},{"p0","p1"})
        self.assertEqual(len(result["snapshots"]),1)
        self.assertEqual(self.store.working(branch["id"])["read_ids"],["p0","p1"])
        self.assertTrue(all("unread_candidates" not in prompt for prompt,kwargs in provider.calls))

    def test_rejects_unread_seed(self):
        cached=copy.deepcopy(self.cached);cached["read_ids"]=["b"]
        self.store.working(self.key,cached)
        with self.assertRaises(ValueError):self.store.reanalyze(self.key,self.config)


if __name__=="__main__":unittest.main()
