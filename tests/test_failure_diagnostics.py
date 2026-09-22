import tempfile
import threading
import unittest
from pathlib import Path

from deepanalyze.codex import CodexError
from deepanalyze.engine import ResearchEngine
from deepanalyze.literature import LiteratureError
from deepanalyze.schemas import DEFAULT_CONFIG
from deepanalyze.store import RunStore


class _FailingLiterature:
    def __init__(self, error):
        self.error = error

    def resolve(self, seed):
        raise self.error


class FailureDiagnosticsTests(unittest.TestCase):
    def run_failure(self, error, draft=False):
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(Path(directory))
            run = store.create("Synthetic bounded research question", {**DEFAULT_CONFIG, "max_iterations": 1})
            if draft:
                store.working(run["id"], {"synthesis_draft": {"id": "draft", "nodes": []}})
            ResearchEngine(object(), _FailingLiterature(error), store).run(run["id"], threading.Event())
            return store.get(run["id"])

    def test_ambiguous_source_is_not_reported_as_authentication(self):
        error = LiteratureError("SECRET raw provider payload")
        error.code = "ambiguous_title"
        run = self.run_failure(error)
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["progress"]["failure_code"], "source_ambiguous")
        self.assertIn("unambiguously identify", run["stop_reason"])
        self.assertNotIn("SECRET", run["stop_reason"])
        self.assertNotIn("authentication", run["stop_reason"].lower())
        self.assertIn("No completed snapshot", run["stop_reason"])

    def test_model_error_is_sanitized_and_draft_message_is_conditional(self):
        error = CodexError("SECRET api key C:\\private\\profile")
        run = self.run_failure(error, draft=True)
        self.assertEqual(run["progress"]["failure_code"], "model_access_failed")
        self.assertIn("saved draft", run["stop_reason"])
        self.assertNotIn("SECRET", run["stop_reason"])
        self.assertNotIn("api key", run["stop_reason"].lower())

    def test_unexpected_error_is_internal_and_private(self):
        run = self.run_failure(RuntimeError("SECRET traceback and local path"))
        self.assertEqual(run["progress"]["failure_code"], "internal_error")
        self.assertIn("internal error", run["stop_reason"])
        self.assertNotIn("SECRET", run["stop_reason"])
        self.assertNotIn("local path", run["stop_reason"])


if __name__ == "__main__":
    unittest.main()
