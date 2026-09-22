import copy
import tempfile
import threading
import unittest
from pathlib import Path

from deepanalyze.store import RunStore


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = RunStore(Path(self.directory.name))
        self.run = self.store.create("A public paper title", {}, "demo")

    def sample(self, iteration=1):
        return {"id": f"snapshot_{iteration}", "iteration": iteration, "nodes": [{"id": "a", "problem": "original"}],
                "edges": [], "metrics": {"depth": 0}, "groups": [], "gaps": []}

    def test_snapshot_is_immutable_and_inputs_are_copied(self):
        incoming = self.sample()
        saved = self.store.add_snapshot(self.run["id"], incoming)
        incoming["nodes"][0]["problem"] = "mutated input"
        saved["nodes"][0]["problem"] = "mutated output"
        self.assertEqual(self.store.snapshot(self.run["id"], "snapshot_1")["nodes"][0]["problem"], "original")
        with self.assertRaises(ValueError):
            self.store.add_snapshot(self.run["id"], self.sample())

    def test_resume_historical_snapshot_is_independent(self):
        self.store.add_snapshot(self.run["id"], self.sample(1))
        self.store.add_snapshot(self.run["id"], self.sample(2))
        original = copy.deepcopy(self.store.get(self.run["id"]))
        branch = self.store.resume(self.run["id"], "snapshot_1")
        self.assertEqual(branch["latest_snapshot"]["iteration"], 1)
        self.assertEqual(branch["parent"]["snapshot_id"], "snapshot_1")
        self.store.add_snapshot(branch["id"], self.sample(3))
        self.assertEqual(self.store.get(self.run["id"]), original)
        self.assertEqual(len(self.store.get(branch["id"])["snapshots"]), 2)

    def test_path_traversal_and_protected_fields_rejected(self):
        for value in ("../outside", "..\\outside", "C:/absolute", "", "a/b"):
            with self.assertRaises(ValueError):
                self.store.get(value)
        with self.assertRaises(ValueError):
            self.store.snapshot(self.run["id"], "../outside")
        with self.assertRaises(ValueError):
            self.store.update(self.run["id"], latest_snapshot={})

    def test_concurrent_events_do_not_lose_updates(self):
        threads = [threading.Thread(target=self.store.event, args=(self.run["id"], "test", f"event {number}")) for number in range(15)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(self.store.get(self.run["id"])["events"]), 15)

    def test_trash_restore_preserves_snapshots_and_reports_compact_metadata(self):
        self.store.add_snapshot(self.run["id"], self.sample())
        trashed = self.store.trash(self.run["id"])
        self.assertEqual(trashed["id"], self.run["id"])
        self.assertEqual(trashed["snapshot_count"], 1)
        self.assertEqual(self.store.list_runs(), [])
        self.assertEqual(self.store.list_trashed()[0]["id"], self.run["id"])
        restored = self.store.restore(self.run["id"])
        self.assertEqual(restored["latest_snapshot"]["id"], "snapshot_1")

    def test_trash_and_restore_collisions_are_safe(self):
        other = self.store.create("Other paper", {}, "demo")
        self.store.trash(self.run["id"])
        with self.assertRaises(KeyError):
            self.store.restore(other["id"] + "missing")
        with self.assertRaises(KeyError):
            self.store.trash(self.run["id"])
        self.store.restore(self.run["id"])
        with self.assertRaises(KeyError):
            self.store.restore(self.run["id"])

    def test_purge_trash_requires_confirmation_and_validates_all_targets_first(self):
        other = self.store.create("Other", {}, "demo")
        self.store.trash(self.run["id"])
        self.store.trash(other["id"])
        with self.assertRaises(ValueError):
            self.store.purge_trash([self.run["id"]], confirm=False)
        with self.assertRaises(KeyError):
            self.store.purge_trash([self.run["id"], "missing"], confirm=True)
        self.assertEqual(len(self.store.list_trashed()), 2)
        self.assertEqual(self.store.purge_trash([self.run["id"]], confirm=True), [self.run["id"]])
        self.assertEqual([item["id"] for item in self.store.list_trashed()], [other["id"]])
    def test_restart_marks_active_runs_interrupted_without_erasing_snapshot(self):
        self.store.add_snapshot(self.run["id"], self.sample())
        self.store.update(self.run["id"], status="running")
        self.assertEqual(self.store.recover_interrupted(), 1)
        restored = self.store.get(self.run["id"])
        self.assertEqual(restored["status"], "interrupted")
        self.assertEqual(restored["latest_snapshot"]["id"], "snapshot_1")

    def test_usage_replaces_cumulative_notifications_without_double_counting(self):
        call_id = self.store.begin_call(self.run["id"], "exploration", "model-x", 1, 42)
        self.store.record_usage(self.run["id"], call_id, {"inputTokens": 10, "outputTokens": 4, "totalTokens": 14})
        self.store.record_usage(self.run["id"], call_id, {"inputTokens": 12, "outputTokens": 5, "totalTokens": 17})
        run = self.store.finish_call(self.run["id"], call_id, "completed")
        self.assertEqual(run["usage"]["total_tokens"], 17)
        self.assertEqual(run["usage"]["reported_calls"], 1)
        self.assertEqual(run["progress"]["model_calls"], 1)
        self.assertIn("completed_at", run["calls"][0])
        self.assertGreaterEqual(run["calls"][0]["elapsed_seconds"], 0)

    def test_partial_usage_counters_remain_unknown(self):
        call_id = self.store.begin_call(self.run["id"], "synthesis", "model-x", 1, 3)
        run = self.store.record_usage(self.run["id"], call_id, {"inputTokens": 9})
        self.assertEqual(run["usage"]["input_tokens"], 9)
        self.assertIsNone(run["usage"]["output_tokens"])
        self.assertIsNone(run["usage"]["total_tokens"])

    def test_legacy_run_usage_is_unknown(self):
        path = self.store._directory(self.run["id"]) / "run.json"
        value = self.store._load(path)
        value.pop("usage", None)
        value.pop("calls", None)
        self.store._write(path, value)
        usage = self.store.get(self.run["id"])["usage"]
        self.assertIsNone(usage["input_tokens"])


if __name__ == "__main__":
    unittest.main()
