"""Loopback-only web application; research data and static assets stay separate."""

from __future__ import annotations

import argparse
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import __version__
from .codex import CodexClient, CodexError
from .engine import ResearchEngine
from .literature import LiteratureClient, LiteratureError
from .schemas import DEFAULT_CONFIG, normalize_config
from .store import RunStore

STATIC = Path(__file__).with_name("static")
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/app.css": ("app.css", "text/css; charset=utf-8"),
    "/static/layout.js": ("layout.js", "text/javascript; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


class Conflict(ValueError):
    def __init__(self, message, code="conflict", active_run_id=None):
        super().__init__(message)
        self.code = code
        self.active_run_id = active_run_id


def standalone_html(snapshot: dict, run: dict) -> str:
    """Export the selected judgments, never a run's events, settings or credentials."""
    payload = {"snapshot": snapshot, "run": {
        key: run.get(key) for key in ("id", "seed", "mode", "created_at")
    }}
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    for char, replacement in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"),
                              ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        encoded = encoded.replace(char, replacement)
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="/static/app.css">', f"<style>{css}</style>")
    scripts = [f"<script>window.__DEEPANALYZE_EXPORT__ = {encoded};</script>"]
    for name in ("layout.js", "app.js"):
        html = html.replace(f'<script src="/static/{name}" defer></script>', "")
        scripts.append(f"<script>{(STATIC / name).read_text(encoding='utf-8')}</script>")
    return html.replace("</body>", "\n".join(scripts) + "\n</body>")



class Application:
    def __init__(self, data_dir: Path, provider=None, literature=None):
        self.data_dir = Path(data_dir).resolve()
        self.store = RunStore(self.data_dir)
        self.store.recover_interrupted()
        self.provider = provider if provider is not None else CodexClient(self.data_dir / "runtime")
        self.literature = literature if literature is not None else LiteratureClient(self.data_dir / "cache")
        self.engine = ResearchEngine(self.provider, self.literature, self.store)
        self.token = secrets.token_urlsafe(32)
        self._lock = threading.RLock()
        self._active: str | None = None
        self._cancel: threading.Event | None = None
        self._worker: threading.Thread | None = None

    def state(self) -> dict:
        with self._lock:
            runs = self.store.list_runs()
            # Large snapshots are fetched only for the selected exploration.
            for run in runs:
                run.pop("latest_snapshot", None)
            return {"version": __version__, "csrf_token": self.token,
                    "runs": runs, "active_run_id": self._active,
                    "default_config": dict(DEFAULT_CONFIG)}

    def _check_idle(self):
        if not self._active:
            return
        worker = self._worker
        if worker is not None and worker.is_alive():
            raise Conflict("An exploration is running. Stop it before starting another.",
                           code="exploration_active", active_run_id=self._active)
        # A stale pointer must be made visible as an interrupted run before a
        # new worker can be launched.
        stale_id = self._active
        try:
            run = self.store.get(stale_id)
            if run["status"] in {"queued", "running", "stopping"}:
                self.store.update(stale_id, status="interrupted", phase="interrupted",
                                  stop_reason="The local worker stopped unexpectedly. Resume a saved snapshot to continue.")
        finally:
            self._active = None
            self._cancel = None
            self._worker = None

    def _require_auth(self, mode):
        if mode == "live":
            status = self.provider.status()
            if not status.get("available") or not status.get("authenticated"):
                raise Conflict("Connect Codex before starting a live exploration.")

    def start(self, seed: str, mode: str, config: dict) -> dict:
        with self._lock:
            self._check_idle()
            if mode not in {"live", "demo"}:
                raise ValueError("Choose live research or the illustrative demo.")
            config = normalize_config(config)
            if mode == "demo":
                seed = "Illustrative research evolution (synthetic demo)"
            if not isinstance(seed, str) or not seed.strip() or len(seed) > 2000:
                raise ValueError("Enter a paper title, DOI, or arXiv link.")
            self._require_auth(mode)
            run = self.store.create(seed, config, mode)
            self._launch(run["id"])
            return self.store.get(run["id"])

    def resume(self, run_id: str, snapshot_id: str, config: dict | None = None) -> dict:
        with self._lock:
            self._check_idle()
            original = self.store.get(run_id)
            self._require_auth(original["mode"])
            run = self.store.resume(run_id, snapshot_id, config=config)
            self._launch(run["id"])
            return self.store.get(run["id"])

    def run_detail(self, run_id: str) -> dict:
        run = self.store.get(run_id)
        draft = self.store.working(run_id).get("synthesis_draft")
        if draft and draft.get("completion_status") == "incomplete":
            # Only normalized analysis is exposed, never the raw extraction cache.
            allowed = {"id", "iteration", "created_at", "seed_id", "scope", "groups", "nodes",
                       "edges", "comparisons", "synthesis_quality", "gaps", "changes", "metrics",
                       "review_notes", "demo", "completion_status", "language", "refinement"}
            run["working_snapshot"] = {key: value for key, value in draft.items() if key in allowed}
            run["working_snapshot"].setdefault("language", run["config"].get("language", "zh"))
        try:
            budget = self.store.synthesis_budget(run_id)
        except (KeyError, ValueError):
            budget = None
        run["synthesis_budget"] = budget
        run["can_retry_synthesis"] = (bool(run.get("working_snapshot"))
            and run["status"] not in {"running", "queued", "stopping"}
            and bool(budget) and budget["remaining_model_calls"] > 0 and budget["remaining_seconds"] > 0
            and not self.store.synthesis_successor(run_id))
        return run

    def reanalyze(self, run_id: str, config: dict) -> dict:
        with self._lock:
            self._check_idle()
            if config is None:
                raise ValueError("A fresh run configuration is required.")
            normalized = normalize_config(config)
            original = self.store.get(run_id)
            self._require_auth(original["mode"])
            run = self.store.reanalyze(run_id, normalized)
            self._launch(run["id"])
            return self.store.get(run["id"])

    def retry_synthesis(self, run_id: str) -> dict:
        with self._lock:
            self._check_idle()
            original = self.store.get(run_id)
            self._require_auth(original["mode"])
            run = self.store.retry_synthesis(run_id)
            self._launch(run["id"])
            return self.run_detail(run["id"])

    def _launch(self, run_id: str):
        self._active = run_id
        self._cancel = threading.Event()
        self._worker = threading.Thread(target=self._work, args=(run_id, self._cancel),
                                        name="deepanalyze-research", daemon=True)
        self._worker.start()

    def _work(self, run_id: str, cancel: threading.Event):
        try:
            self.engine.run(run_id, cancel)
            current = self.store.get(run_id)
            if current["status"] in {"queued", "running", "stopping"}:
                self.store.update(run_id, status="interrupted", phase="interrupted",
                                  stop_reason="The local worker stopped unexpectedly. Resume a saved snapshot to continue.")
        except Exception:
            # Network responses, paths and model output are not safe public errors.
            self.store.update(run_id, status="failed", phase="failed",
                              stop_reason="The exploration failed. Completed snapshots are preserved.")
            self.store.event(run_id, "failed", "The local worker stopped unexpectedly. Try a new run or resume a saved snapshot.")
        finally:
            with self._lock:
                if self._active == run_id:
                    self._active = None

    def trash(self, run_id: str) -> dict:
        with self._lock:
            if self._active == run_id:
                worker = self._worker
                if worker is not None and worker.is_alive():
                    raise Conflict("Stop the active exploration before moving it to trash.",
                                   code="run_active", active_run_id=run_id)
                self._check_idle()
            return self.store.trash(run_id)

    def purge_trash(self, run_ids, confirm=False) -> dict:
        with self._lock:
            if self._active and self._active in (run_ids if isinstance(run_ids, list) else []):
                raise Conflict("Stop the active exploration before purging it from trash.", code="run_active", active_run_id=self._active)
            return {"deleted_ids": self.store.purge_trash(run_ids, confirm=confirm)}
    def restore(self, run_id: str) -> dict:
        with self._lock:
            # Restoring history does not launch work and is safe alongside an
            # unrelated active exploration.
            return self.store.restore(run_id)

    def stop(self, run_id: str) -> dict:
        with self._lock:
            run = self.store.get(run_id)
            if self._active == run_id and self._cancel:
                self._cancel.set()
                if run["status"] in {"queued", "running"}:
                    self.store.update(run_id, status="stopping", phase="stopping")
            return self.store.get(run_id)

    def auth_action(self, action, payload):
        with self._lock:
            if self._active and self.store.get(self._active)["mode"] == "live":
                raise Conflict("Stop the live exploration before changing its model connection.")
            if action == "logout":
                return self.provider.logout()
            method = payload.get("method")
            if method not in {"chatgpt", "apiKey"}:
                raise ValueError("Choose ChatGPT login or API key authentication.")
            key = payload.get("api_key")
            if method == "apiKey" and (not isinstance(key, str) or not key.strip() or len(key) > 4096):
                raise ValueError("Enter a valid API key in the connection dialog.")
            return self.provider.login(method, api_key=key)

    def close(self):
        if self._cancel:
            self._cancel.set()
        if self._worker:
            self._worker.join(timeout=3)
        self.provider.close()


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port: int, app: Application):
        self.app = app
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "DeepAnalyze"
    sys_version = ""

    def log_message(self, format, *args):
        # Request URLs, queries and bodies may contain private research inputs.
        pass

    @property
    def app(self) -> Application:
        return self.server.app

    def _local(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host", "").lower() not in hosts:
            self._json({"error": "Only the local application host is allowed."}, 403)
            return False
        origin = self.headers.get("Origin")
        if origin and origin.lower() not in {f"http://{host}" for host in hosts}:
            self._json({"error": "Cross-origin requests are not allowed."}, 403)
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self._json({"error": "Cross-site requests are not allowed."}, 403)
            return False
        return True

    def _send(self, body: bytes, kind: str, status=200, filename=None):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, value, status=200):
        self._send(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                   "application/json; charset=utf-8", status)

    def do_GET(self):
        if not self._local():
            return
        try:
            parsed = urlsplit(self.path)
            parts = parsed.path.strip("/").split("/")
            if parsed.path in ASSETS:
                name, kind = ASSETS[parsed.path]
                self._send((STATIC / name).read_bytes(), kind)
            elif parsed.path == "/api/state":
                self._json(self.app.state())
            elif parsed.path == "/api/auth/status":
                self._json(self.app.provider.status())
            elif parsed.path == "/api/trash":
                self._json(self.app.store.list_trashed())
            elif len(parts) >= 3 and parts[:2] == ["api", "runs"]:
                run_id = parts[2]
                if len(parts) == 3:
                    self._json(self.app.run_detail(run_id))
                elif len(parts) == 5 and parts[3] == "snapshots":
                    self._json(self.app.store.snapshot(run_id, parts[4]))
                elif len(parts) == 4 and parts[3] == "export":
                    run = self.app.store.get(run_id)
                    selected = parse_qs(parsed.query).get("snapshot", [None])[0]
                    snapshot = self.app.store.snapshot(run_id, selected) if selected else run.get("latest_snapshot")
                    if not snapshot:
                        raise Conflict("No completed snapshot is available to export yet.")
                    self._send(standalone_html(snapshot, run).encode("utf-8"), "text/html; charset=utf-8",
                               filename="DeepAnalyze-research.html")
                else:
                    self._json({"error": "Not found."}, 404)
            else:
                self._json({"error": "Not found."}, 404)
        except Exception as exc:
            self._error(exc)

    def do_POST(self):
        if not self._local():
            return
        supplied_token = self.headers.get("X-DeepAnalyze-Token", "").encode("utf-8")
        if not secrets.compare_digest(supplied_token, self.app.token.encode("ascii")):
            # Consume a small, declared body before rejecting. This prevents
            # Windows clients from seeing a TCP reset when they already sent
            # an ordinary-sized POST body, while avoiding an attacker-controlled
            # unbounded drain.
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except (TypeError, ValueError):
                length = 0
            if 0 < length <= 65536:
                self.connection.settimeout(2)
                try:
                    self.rfile.read(length)
                except OSError:
                    self.close_connection = True
            self._json({"error": "Refresh the local page before making changes."}, 403)
            return
        try:
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Send JSON in the request body.")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                self._json({"error": "Request body must be between 1 byte and 64 KB."}, 413)
                return
            self.connection.settimeout(15)
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be an object.")
            path = urlsplit(self.path).path
            parts = path.strip("/").split("/")
            if path in {"/api/auth/login", "/api/auth/logout"}:
                self._json(self.app.auth_action(parts[-1], payload))
            elif path == "/api/trash/purge":
                self._json(self.app.purge_trash(payload.get("run_ids"), payload.get("confirm")))
            elif path == "/api/runs":
                self._json(self.app.start(payload.get("seed", ""), payload.get("mode", "live"), payload.get("config", {})), 201)
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "stop":
                self._json(self.app.stop(parts[2]))
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "trash":
                self._json(self.app.trash(parts[2]))
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "restore":
                self._json(self.app.restore(parts[2]))
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "retry-synthesis":
                self._json(self.app.retry_synthesis(parts[2]), 201)
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "reanalyze":
                if "config" not in payload:
                    raise ValueError("A fresh run configuration is required.")
                self._json(self.app.reanalyze(parts[2], payload.get("config")), 201)
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "resume":
                self._json(self.app.resume(parts[2], payload.get("snapshot_id", ""), payload.get("config")), 201)
            else:
                self._json({"error": "Not found."}, 404)
        except Exception as exc:
            self._error(exc)

    def _error(self, exc):
        if isinstance(exc, Conflict):
            body = {"error": str(exc), "code": exc.code}
            if exc.active_run_id:
                body["active_run_id"] = exc.active_run_id
            self._json(body, 409)
        elif isinstance(exc, (CodexError, LiteratureError)):
            self._json({"error": str(exc)}, 502)
        elif isinstance(exc, KeyError):
            self._json({"error": "Requested run or snapshot was not found."}, 404)
        elif isinstance(exc, (ValueError, TypeError)):
            # Some parse errors echo input. Keep the public boundary generic.
            self._json({"error": "Invalid request. Check the paper identifier, settings and selected snapshot."}, 400)
        else:
            self._json({"error": "The local application could not complete this request."}, 500)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explore the problems behind research progress.")
    parser.add_argument("--port", type=int, default=8765, help="Loopback web port (default: 8765)")
    parser.add_argument("--data-dir", type=Path, default=Path(".deepanalyze"), help="Private local run storage")
    parser.add_argument("--open", action="store_true", help="Open the local browser page")
    parser.add_argument("--demo", action="store_true", help="Start an offline synthetic demonstration")
    parser.add_argument("--seed", default="", help="Immediately start live research for this paper")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535.")
    if args.demo and args.seed:
        parser.error("Choose --demo or --seed.")
    app = Application(args.data_dir)
    try:
        server = LocalServer(args.port, app)
    except OSError:
        app.close()
        parser.exit(1, "Cannot open the local port. Try --port with a different number.\n")
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"DeepAnalyze {__version__} · {url}", flush=True)
    print("Keep this terminal open. Press Ctrl+C to stop.", flush=True)
    try:
        if args.demo or args.seed:
            try:
                app.start(args.seed, "demo" if args.demo else "live", {})
            except (Conflict, CodexError) as exc:
                print(str(exc), flush=True)
        if args.open:
            webbrowser.open(url)
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.close()


if __name__ == "__main__":
    main()
