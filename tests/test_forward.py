import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

from deepanalyze.engine import ResearchEngine
from deepanalyze.schemas import normalize_config
from deepanalyze.store import RunStore
from tests.test_engine import FakeLiterature, FakeProvider


class ForwardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = RunStore(Path(self.temp.name))

    def test_language_reaches_both_roles_and_snapshot_without_changing_quotes(self):
        self.assertEqual(normalize_config()["language"], "zh")
        with self.assertRaises(ValueError):
            normalize_config({"language": "fr"})
        for language in ("zh", "en"):
            provider = FakeProvider()
            run = self.store.create("seed", {"max_iterations": 1, "language": language})
            ResearchEngine(provider, FakeLiterature(), self.store).run(run["id"], threading.Event())
            snapshot = self.store.get(run["id"])["latest_snapshot"]
            self.assertEqual(snapshot["language"], language)
            for prompt, _ in provider.calls:
                data = json.loads(prompt.split("\nDATA:\n")[1])
                self.assertEqual(data["output_language"], language)
            seed = next(n for n in snapshot["nodes"] if n["id"] == "p0")
            self.assertEqual(seed["evidence"][0]["quote"], "This synthetic source 0 changes a bounded table operation.")
