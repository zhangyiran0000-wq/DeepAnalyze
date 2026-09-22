import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from deepanalyze.server import Application, Handler, LocalServer, standalone_html


class OfflineProvider:
    def status(self):
        return {"available": True, "authenticated": False, "mode": None}

    def close(self):
        pass

    def generate(self, *args, **kwargs):
        raise AssertionError("Demo must never call a model.")


class NoLiterature:
    def __getattr__(self, name):
        raise AssertionError("Demo must never retrieve literature.")


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Application(Path(self.temp.name), OfflineProvider(), NoLiterature())
        self.server = LocalServer(0, self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.app.close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method, path, data=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        fields = {"Content-Type": "application/json", **(headers or {})}
        connection.request(method, path, json.dumps(data) if data is not None else None, fields)
        response = connection.getresponse()
        body = response.read()
        result = (response.status, dict(response.getheaders()), body)
        connection.close()
        return result

    def post(self, path, data):
        return self.request("POST", path, data, {"X-DeepAnalyze-Token": self.app.token})

    def finished(self, run_id):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            run = self.app.store.get(run_id)
            if run["status"] in {"completed", "failed", "stopped", "budget_exhausted"} and self.app.state()["active_run_id"] is None:
                return run
            time.sleep(0.025)
        self.fail("The local worker did not finish.")

    def test_cross_origin_rebinding_and_mutations_are_blocked(self):
        self.assertEqual(self.request("GET", "/api/state", headers={"Host": "malicious.example"})[0], 403)
        self.assertEqual(self.request("GET", "/api/state", headers={"Origin": "https://example.test"})[0], 403)
        self.assertEqual(self.request("POST", "/api/runs", {"mode": "demo"})[0], 403)
        # Validate non-ASCII tokens directly: some Windows network filters reject
        # a Latin-1 header before the local Python server receives it.
        handler = Handler.__new__(Handler)
        handler.server = self.server
        handler.headers = {"X-DeepAnalyze-Token": chr(233)}
        handler._local = lambda: True
        replies = []
        handler._json = lambda value, status=200: replies.append(status)
        handler.do_POST()
        self.assertEqual(replies, [403])
        self.assertEqual(self.request("GET", "/api/state", headers={"Sec-Fetch-Site": "cross-site"})[0], 403)

    def test_private_files_never_become_static_routes(self):
        for path in ("/Intention.md", "/.env", "/.deepanalyze/runs", "/static/../Intention.md", "/static/%2e%2e/Intention.md", "/main.py"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 404)
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"DeepAnalyze", body)
        self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_demo_history_branch_and_export_end_to_end(self):
        status, _, body = self.post("/api/runs", {"mode": "demo", "config": {"max_iterations": 2}})
        self.assertEqual(status, 201)
        run_id = json.loads(body)["id"]
        conflict_status, _, conflict_body = self.post("/api/runs", {"mode": "demo"})
        self.assertEqual(conflict_status, 409)
        conflict = json.loads(conflict_body)
        self.assertEqual(conflict["code"], "exploration_active")
        self.assertEqual(conflict["active_run_id"], run_id)
        run = self.finished(run_id)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(len(run["snapshots"]), 2)
        first = run["snapshots"][0]["id"]
        selected = self.app.store.snapshot(run_id, first)
        status, headers, body = self.request("GET", f"/api/runs/{run_id}/export?snapshot={first}")
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn(b"window.__DEEPANALYZE_EXPORT__", body)
        self.assertIn(first.encode(), body)
        self.assertNotIn(b'src="/static/app.js"', body)
        self.assertNotIn(b'src="/static/layout.js"', body)
        self.assertIn(b"DeepAnalyzeLayout", body)
        self.assertEqual(self.request("GET", "/static/layout.js")[0], 200)
        self.assertNotIn(b'href="/static/app.css"', body)
        self.assertNotIn(self.app.token.encode(), body)
        status, _, body = self.post(f"/api/runs/{run_id}/resume", {"snapshot_id": first})
        self.assertEqual(status, 201)
        branch = self.finished(json.loads(body)["id"])
        self.assertEqual(branch["parent"]["snapshot_id"], first)
        self.assertEqual(self.app.store.snapshot(run_id, first), selected)
        self.assertEqual(len(self.app.store.get(run_id)["snapshots"]), 2)

    def test_stale_active_pointer_is_reconciled_before_new_run(self):
        run = self.app.store.create("stale", {}, "demo")
        self.app.store.update(run["id"], status="running")
        with self.app._lock:
            self.app._active = run["id"]
            self.app._worker = None
            self.app._cancel = None
        self.app._check_idle()
        self.assertIsNone(self.app._active)
        self.assertEqual(self.app.store.get(run["id"])["status"], "interrupted")

    def test_trash_restore_endpoints_require_csrf_and_preserve_run(self):
        run = self.app.store.create("Trash me", {}, "demo")
        self.assertEqual(self.request("GET", "/api/trash")[0], 200)
        no_token = self.request("POST", f"/api/runs/{run['id']}/trash", {})
        self.assertEqual(no_token[0], 403)
        self.assertEqual(self.post(f"/api/runs/{run['id']}/trash", {})[0], 200)
        listing = json.loads(self.request("GET", "/api/trash")[2])
        self.assertEqual(listing[0]["id"], run["id"])
        self.assertEqual(self.request("GET", f"/api/runs/{run['id']}")[0], 404)
        self.assertEqual(self.post(f"/api/runs/{run['id']}/restore", {})[0], 200)
        self.assertEqual(self.app.store.get(run["id"])["seed"], "Trash me")

    def test_trash_purge_requires_csrf_and_deletes_only_explicit_trashed_ids(self):
        first = self.app.store.create("First", {}, "demo")
        second = self.app.store.create("Second", {}, "demo")
        self.app.store.trash(first["id"])
        self.app.store.trash(second["id"])
        self.assertEqual(self.request("POST", "/api/trash/purge", {"run_ids": [first["id"]], "confirm": True})[0], 403)
        status, _, body = self.post("/api/trash/purge", {"run_ids": [first["id"]], "confirm": True})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["deleted_ids"], [first["id"]])
        self.assertEqual([item["id"] for item in self.app.store.list_trashed()], [second["id"]])
        self.assertEqual(self.post("/api/trash/purge", {"run_ids": ["missing"], "confirm": True})[0], 404)
    def test_restore_preserves_unrelated_active_run(self):
        trashed = self.app.store.create("History", {}, "demo")
        self.app.store.trash(trashed["id"])
        active = self.app.store.create("Active", {}, "demo")
        with self.app._lock:
            self.app._active = active["id"]
            self.app._worker = threading.current_thread()
        restored = self.app.restore(trashed["id"])
        self.assertEqual(restored["id"], trashed["id"])
        self.assertEqual(self.app._active, active["id"])
        with self.app._lock:
            self.app._active = None
            self.app._worker = None

    def test_active_run_cannot_be_trashed(self):
        run = self.app.store.create("Active", {}, "demo")
        with self.app._lock:
            self.app._active = run["id"]
            self.app._worker = threading.current_thread()
        with self.assertRaises(Exception) as caught:
            self.app.trash(run["id"])
        self.assertEqual(getattr(caught.exception, "code", None), "run_active")
        with self.app._lock:
            self.app._active = None
            self.app._worker = None

    def test_stop_keeps_completed_snapshots_and_live_requires_login(self):
        self.assertEqual(self.post("/api/runs", {"seed": "An example paper", "mode": "live"})[0], 409)
        _, _, body = self.post("/api/runs", {"mode": "demo"})
        run_id = json.loads(body)["id"]
        self.assertEqual(self.post(f"/api/runs/{run_id}/stop", {})[0], 200)
        run = self.finished(run_id)
        self.assertEqual(run["status"], "stopped")

    def test_export_escapes_snapshot_text_and_omits_runtime_data(self):
        html = standalone_html({"nodes": [{"title": "</script><script>malicious()</script>"}]},
                               {"seed": "A seed", "config": {"private": "DO-NOT-EXPORT"}, "events": ["SECRET"]})
        self.assertNotIn("</script><script>malicious()", html)
        self.assertIn("\\u003c/script\\u003e", html)
        self.assertNotIn("DO-NOT-EXPORT", html)
        self.assertNotIn('"SECRET"', html)


if __name__ == "__main__":
    unittest.main()
