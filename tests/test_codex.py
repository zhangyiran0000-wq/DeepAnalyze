"""Protocol tests never launch Codex, change credentials, or spend tokens."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import queue
import tempfile
import threading
import unittest
from unittest.mock import patch

from deepanalyze.codex import CodexCancelled, CodexClient, CodexError, _find_executable


class _Pipe:
    def __init__(self):
        self.lines = queue.Queue()

    def __iter__(self):
        while True:
            line = self.lines.get()
            if line is None:
                return
            yield line

    def close(self):
        self.lines.put(None)


class _Input:
    def __init__(self, process):
        self.process = process

    def write(self, text):
        self.process.receive(json.loads(text))

    def flush(self):
        pass

    def close(self):
        pass


class FakeProcess:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.options = kwargs
        self.stdout = _Pipe()
        self.stdin = _Input(self)
        self.returncode = None
        self.messages = []
        self.authenticated = True
        self.mode = "chatgpt"
        self.hold = False
        self.reject = None
        self.invalid_json = False
        self.drop_turn_response = False
        self.thread_count = 0
        self.turn_started = threading.Event()

    def send(self, message):
        self.stdout.lines.put(json.dumps(message) + "\n")

    def notify(self, method, params):
        self.send({"method": method, "params": params})

    def receive(self, message):
        self.messages.append(message)
        method = message.get("method")
        if method is None or "id" not in message:
            return
        if method == self.reject:
            self.send({"id": message["id"], "error": {
                "code": -1, "message": "private@example.test sk-secret-personal-path"}})
            return
        result = {}
        if method == "account/read":
            result = {"account": {"type": self.mode, "email": "private@example.test",
                                   "planType": "private-plan"} if self.authenticated else None}
        elif method == "account/login/start":
            self.mode = message["params"]["type"]
            if self.mode == "apiKey":
                result = {"type": "apiKey"}
            else:
                result = {"type": "chatgpt", "loginId": "login-1",
                          "authUrl": "https://auth.openai.com/authorize?state=opaque"}
                self.notify("account/login/completed", {
                    "loginId": "login-1", "success": False,
                    "error": "private@example.test sk-secret"})
        elif method == "account/logout":
            self.authenticated = False
        elif method == "config/read":
            result = {"config": {"model_reasoning_effort": "ultra", "mcp_servers": {"private-server": {"env": {"secret": "private"}}},
                                  "plugins": {"local-plugin": {"enabled": True}}}}
        elif method == "thread/start":
            self.thread_count += 1
            result = {"thread": {"id": f"thread-{self.thread_count}"}}
        elif method == "turn/start":
            thread_id = message["params"]["threadId"]
            turn_id = f"turn-{thread_id}"
            result = {"turn": {"id": turn_id}}
            self.turn_started.set()
            if not self.hold:
                self.notify("item/completed", {
                    "threadId": thread_id, "turnId": turn_id,
                    "item": {"type": "agentMessage", "text": "analysis preamble"}})
                self.notify("thread/tokenUsage/updated", {
                    "threadId": thread_id, "turnId": turn_id,
                    "tokenUsage": {"total": {"inputTokens": 10, "outputTokens": 4,
                                              "totalTokens": 14, "secret": "private"}}})
                self.notify("item/completed", {
                    "threadId": thread_id, "turnId": turn_id,
                    "item": {"type": "agentMessage", "text": "not-json-private@example.test"
                             if self.invalid_json else json.dumps({"thread": thread_id})}})
                self.notify("turn/completed", {
                    "threadId": thread_id, "turn": {"id": turn_id, "status": "completed",
                                                   "items": [], "error": None}})
            if self.drop_turn_response:
                return
        self.send({"id": message["id"], "result": result})

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0
        self.stdout.close()

    kill = terminate

    def wait(self, timeout=None):
        return self.returncode


class CodexTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.process = FakeProcess()
        self.popen = patch("deepanalyze.codex.subprocess.Popen", return_value=self.process)
        self.spawn = self.popen.start()
        self.capabilities = patch.object(CodexClient, "_check_capabilities")
        self.capabilities.start()
        self.client = CodexClient(Path(self.temporary.name), executable="codex")

    def tearDown(self):
        self.client.close()
        self.capabilities.stop()
        self.popen.stop()
        self.temporary.cleanup()

    def test_status_is_read_only_and_sanitized(self):
        result = self.client.status()
        self.assertEqual(result, {"available": True, "authenticated": True, "mode": "chatgpt"})
        self.assertEqual([m.get("method") for m in self.process.messages],
                         ["initialize", "initialized", "account/read"])
        self.assertNotIn("private", json.dumps(result))
        self.assertNotEqual(self.spawn.call_args.kwargs["cwd"], self.temporary.name)
        self.assertEqual(self.spawn.call_args.kwargs["encoding"], "utf-8")

    def test_missing_executable_does_not_launch(self):
        with patch("deepanalyze.codex.shutil.which", return_value=None), \
                patch.dict("os.environ", {}, clear=True):
            client = CodexClient(Path(self.temporary.name))
        self.assertFalse(client.status()["available"])
        self.spawn.assert_not_called()
        client.close()

    def test_windows_prefers_native_runtime_over_npm_wrapper(self):
        with patch("deepanalyze.codex.os.name", "nt"), \
                patch.dict("os.environ", {}, clear=True), \
                patch("deepanalyze.codex.shutil.which") as which:
            which.side_effect = lambda name: "native-codex.exe" if name == "codex.exe" else "codex.cmd"
            self.assertEqual(_find_executable(None), "native-codex.exe")
            self.assertEqual(_find_executable("chosen-runtime"), "chosen-runtime")
            which.assert_called_once_with("codex.exe")

    def test_windows_uses_wrapper_if_native_is_unavailable(self):
        with patch("deepanalyze.codex.os.name", "nt"), \
                patch.dict("os.environ", {}, clear=True), \
                patch("deepanalyze.codex.shutil.which", side_effect=[None, "codex.cmd"]):
            self.assertEqual(_find_executable(None), "codex.cmd")

    def test_generate_new_isolated_thread_and_structured_result(self):
        progress = []
        schema = {"type": "object", "properties": {"thread": {"type": "string"}},
                  "required": ["thread"], "additionalProperties": False}
        first = self.client.generate("Analyze public evidence", schema, model="configured-model",
                                     on_event=progress.append)
        second = self.client.generate("A separate batch")
        self.assertNotEqual(first["thread_id"], second["thread_id"])
        self.assertEqual(first["data"], {"thread": first["thread_id"]})
        self.assertEqual(first["usage"], {"inputTokens": 10, "outputTokens": 4, "totalTokens": 14})
        starts = [m["params"] for m in self.process.messages if m.get("method") == "thread/start"]
        self.assertEqual(starts[0]["environments"], [])
        self.assertEqual(starts[0]["config"]["model_reasoning_effort"], "medium")
        self.assertEqual(starts[0]["sandbox"], "read-only")
        self.assertEqual(starts[0]["approvalPolicy"], "never")
        self.assertTrue(starts[0]["ephemeral"])
        self.assertFalse(starts[0]["config"]["mcp_servers"]["private-server"]["enabled"])
        self.assertFalse(starts[0]["config"]["plugins"]["local-plugin"]["enabled"])
        turn = next(m["params"] for m in self.process.messages if m.get("method") == "turn/start")
        self.assertEqual(turn["outputSchema"], schema)
        self.assertEqual(turn["environments"], [])
        self.assertEqual(turn["sandboxPolicy"], {"type": "readOnly", "networkAccess": False})
        self.assertEqual(len(progress), 2)
        self.assertNotIn("private", " ".join(progress))

    def test_low_reasoning_override_is_local_to_keyword_call(self):
        self.client.generate("Extract keywords", reasoning_effort="low")
        self.client.generate("Synthesize research")
        starts = [m["params"] for m in self.process.messages if m.get("method") == "thread/start"]
        self.assertEqual(starts[0]["config"]["model_reasoning_effort"], "low")
        self.assertEqual(starts[1]["config"]["model_reasoning_effort"], "medium")
        with self.assertRaises(CodexError):
            self.client.generate("bad override", reasoning_effort="unknown")

    def test_concurrent_generations_dispatch_by_thread(self):
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(self.client.generate, ["one", "two", "three"]))
        self.assertEqual(len({r["thread_id"] for r in results}), 3)
        for result in results:
            self.assertEqual(result["thread_id"], result["data"]["thread"])

    def test_cancel_interrupts_active_turn(self):
        self.process.hold = True
        cancel = threading.Event()
        usage_updates = []
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.client.generate, "evidence", cancel_event=cancel,
                                     on_usage=usage_updates.append)
            self.assertTrue(self.process.turn_started.wait(2))
            cancel.set()
            with self.assertRaises(CodexCancelled):
                future.result(timeout=2)
        interrupt = next(m for m in self.process.messages if m.get("method") == "turn/interrupt")
        self.assertEqual(interrupt["params"]["threadId"], "thread-1")
        self.assertTrue(usage_updates)
        self.assertEqual(usage_updates[-1], {})

    def test_timeout_interrupts_active_turn(self):
        self.process.hold = True
        with self.assertRaisesRegex(CodexError, "timed out"):
            self.client.generate("evidence", timeout=0.04)
        self.assertIn("turn/interrupt", [m.get("method") for m in self.process.messages])

    def test_unknown_started_turn_closes_transport_on_timeout(self):
        self.process.hold = True
        self.process.drop_turn_response = True
        with self.assertRaises(CodexError):
            self.client.generate("evidence", timeout=0.04)
        self.assertIsNotNone(self.process.poll())

    def test_cancelled_before_start_does_not_launch(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(CodexCancelled):
            self.client.generate("evidence", cancel_event=cancel)
        self.spawn.assert_not_called()

    def test_errors_do_not_echo_credentials_or_model_text(self):
        self.process.reject = "account/read"
        result = self.client.status()
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("sk-secret", json.dumps(result))
        self.process.reject = None
        self.process.invalid_json = True
        with self.assertRaises(CodexError) as caught:
            self.client.generate("evidence")
        self.assertNotIn("private", str(caught.exception))

    def test_explicit_login_and_sanitized_async_completion(self):
        result = self.client.login("chatgpt")
        self.assertEqual(result["login_id"], "login-1")
        self.assertTrue(result["auth_url"].startswith("https://auth.openai.com/"))
        status = self.client.status()
        self.assertIn("error", status)
        self.assertNotIn("private", json.dumps(status))
        self.assertTrue(self.client.login("apiKey", "sk-example-value")["authenticated"])
        self.assertFalse(self.client.logout()["authenticated"])

    def test_server_requests_are_denied(self):
        self.client.status()
        self.client._deny_request({"id": "server-1", "method": "item/commandExecution/requestApproval"})
        self.client._deny_request({"id": "server-2", "method": "item/tool/call"})
        self.assertEqual(self.process.messages[-2]["result"], {"decision": "decline"})
        self.assertEqual(self.process.messages[-1]["error"]["code"], -32601)

    def test_capability_gate_fails_closed(self):
        self.capabilities.stop()
        with patch("deepanalyze.codex.subprocess.run") as run:
            run.return_value.returncode = 1
            with self.assertRaisesRegex(CodexError, "disabled environment"):
                self.client.generate("evidence")
        self.assertNotIn("turn/start", [m.get("method") for m in self.process.messages])
        self.capabilities.start()


if __name__ == "__main__":
    unittest.main()
