"""Private, atomic run storage with immutable, independently forkable snapshots."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import stat
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .schemas import normalize_config

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")
_ROOT_LOCKS: dict[str, threading.RLock] = {}
_ROOT_LOCKS_GUARD = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_id(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("Invalid run or snapshot identifier.")
    return value


class RunStore:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._runs = self.root / "runs"
        self._trash = self.root / "trash"
        self._runs.mkdir(exist_ok=True)
        self._trash.mkdir(exist_ok=True)
        if self._runs.resolve().parent != self.root or self._trash.resolve().parent != self.root:
            raise ValueError("Run storage must stay inside its supplied root.")
        with _ROOT_LOCKS_GUARD:
            self._lock = _ROOT_LOCKS.setdefault(str(self.root), threading.RLock())

    def _directory(self, run_id: str) -> Path:
        path = self._runs / safe_id(run_id)
        if path.resolve().parent != self._runs.resolve():
            raise ValueError("Run path must stay inside its storage directory.")
        return path

    def _trash_directory(self, run_id: str) -> Path:
        path = self._trash / safe_id(run_id)
        if path.resolve().parent != self._trash.resolve():
            raise ValueError("Trash path must stay inside its storage directory.")
        return path

    def _load(self, path: Path) -> dict:
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("Stored files must stay inside the supplied root.")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise KeyError("Requested run or snapshot was not found.") from exc

    def _write(self, path: Path, value: dict) -> None:
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("Stored files must stay inside the supplied root.")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def create(self, seed, config, mode="live", parent=None) -> dict:
        if not isinstance(seed, str) or not seed.strip() or len(seed) > 2000:
            raise ValueError("Provide a paper title, DOI, or URL (up to 2,000 characters).")
        if mode not in {"live", "demo"}:
            raise ValueError("Mode must be live or demo.")
        config = normalize_config(config)
        with self._lock:
            now = utc_now()
            run = {
                "id": uuid.uuid4().hex, "seed": seed.strip(), "mode": mode,
                "config": config, "status": "queued", "phase": "queued",
                "iteration": 0, "created_at": now, "updated_at": now,
                "stop_reason": "", "parent": copy.deepcopy(parent),
                "progress": {"candidates": 0, "read": 0, "included": 0,
                             "model_calls": 0, "elapsed_seconds": 0},
                "events": [], "snapshots": [], "latest_snapshot": None,
                "usage": {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0,
                          "total_tokens": 0, "reasoning_output_tokens": 0,
                          "reported_calls": 0, "unreported_calls": 0},
                "calls": [],
            }
            self._write(self._directory(run["id"]) / "run.json", run)
            return copy.deepcopy(run)

    def get(self, run_id) -> dict:
        with self._lock:
            run = self._load(self._directory(run_id) / "run.json")
            # Older run files predate accounting; expose an explicit unknown
            # aggregate without rewriting historical data.
            if "usage" not in run:
                run["usage"] = {"input_tokens": None, "output_tokens": None,
                                 "cached_input_tokens": None, "total_tokens": None,
                                 "reasoning_output_tokens": None, "reported_calls": 0,
                                 "unreported_calls": run.get("progress", {}).get("model_calls", 0)}
            run.setdefault("calls", [])
            return run

    def list_runs(self) -> list[dict]:
        with self._lock:
            result = []
            for path in self._runs.glob("*/run.json"):
                try:
                    if _ID.fullmatch(path.parent.name):
                        result.append(self.get(path.parent.name))
                except (OSError, ValueError, KeyError):
                    continue
            return sorted(result, key=lambda run: run["created_at"], reverse=True)

    def trash(self, run_id) -> dict:
        with self._lock:
            source = self._directory(run_id)
            if not source.is_dir():
                raise KeyError("Requested run or snapshot was not found.")
            destination = self._trash_directory(run_id)
            if destination.exists():
                raise ValueError("A trashed run with this identifier already exists.")
            # Both paths are validated direct children of their respective
            # private roots before the atomic move.
            os.replace(source, destination)
            # Directory mtime can survive a rename on some filesystems;
            # refresh it so list_trashed reflects the actual trash action.
            os.utime(destination, None)
            return self._compact_trashed(run_id, destination)

    def purge_trash(self, run_ids, confirm=False) -> list[str]:
        """Permanently remove only explicitly confirmed, validated trash entries."""
        if type(confirm) is not bool or confirm is not True:
            raise ValueError("Trash purge requires confirm=true.")
        if not isinstance(run_ids, list) or not run_ids or len(run_ids) > 100:
            raise ValueError("Provide a bounded, non-empty list of run IDs.")
        if any(not isinstance(run_id, str) for run_id in run_ids) or len(set(run_ids)) != len(run_ids):
            raise ValueError("Run IDs must be unique strings.")
        with self._lock:
            ids = [safe_id(run_id) for run_id in run_ids]
            trash_root = self._trash.resolve(strict=True)
            if trash_root.parent != self.root or trash_root.is_symlink():
                raise ValueError("Trash storage is not a safe directory.")
            targets = []
            for run_id in ids:
                target = self._trash_directory(run_id)
                if not target.is_dir() or target.is_symlink():
                    raise KeyError("Requested trashed run was not found.")
                resolved = target.resolve(strict=True)
                if resolved.parent != trash_root or not resolved.is_dir():
                    raise ValueError("Trash target must stay inside the intended trash directory.")
                self._assert_no_links(resolved)
                targets.append((run_id, resolved))
            for _, target in targets:
                shutil.rmtree(target)
            return ids

    @staticmethod
    def _assert_no_links(directory: Path) -> None:
        for current, dirs, files in os.walk(directory, followlinks=False):
            current_path = Path(current)
            if current_path.is_symlink() or getattr(current_path.stat(follow_symlinks=False), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValueError("Trash entries cannot contain links or reparse points.")
            for name in [*dirs, *files]:
                path = current_path / name
                info = path.stat(follow_symlinks=False)
                if path.is_symlink() or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                    raise ValueError("Trash entries cannot contain links or reparse points.")
    def restore(self, run_id) -> dict:
        with self._lock:
            source = self._trash_directory(run_id)
            if not source.is_dir():
                raise KeyError("Requested trashed run was not found.")
            destination = self._directory(run_id)
            if destination.exists():
                raise ValueError("A run with this identifier already exists.")
            os.replace(source, destination)
            return self.get(run_id)

    def _compact_trashed(self, run_id, directory) -> dict:
        run = self._load(directory / "run.json")
        return {"id": run_id, "seed": run.get("seed", ""), "mode": run.get("mode"),
                "status": run.get("status"), "phase": run.get("phase"),
                "created_at": run.get("created_at"), "updated_at": run.get("updated_at"),
                "iteration": run.get("iteration", 0),
                "snapshot_count": len(run.get("snapshots", [])),
                "trashed_at": datetime.fromtimestamp(directory.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")}

    def list_trashed(self) -> list[dict]:
        with self._lock:
            result = []
            for directory in self._trash.iterdir():
                try:
                    if directory.is_dir() and _ID.fullmatch(directory.name):
                        result.append(self._compact_trashed(directory.name, directory))
                except (OSError, ValueError, KeyError, json.JSONDecodeError):
                    continue
            return sorted(result, key=lambda item: item.get("trashed_at", ""), reverse=True)

    def update(self, run_id, **patch) -> dict:
        protected = {"id", "created_at", "snapshots", "latest_snapshot", "parent"}
        if protected & patch.keys():
            raise ValueError("Immutable run fields cannot be patched.")
        allowed = {"seed", "mode", "config", "status", "phase", "iteration", "stop_reason", "progress", "events", "budget_carry", "recovery_child_id"}
        if set(patch) - allowed:
            raise ValueError("Unknown run field.")
        with self._lock:
            run = self.get(run_id)
            run.update(copy.deepcopy(patch))
            run["updated_at"] = utc_now()
            self._write(self._directory(run_id) / "run.json", run)
            return copy.deepcopy(run)

    @staticmethod
    def _clean_usage(usage) -> dict:
        if not isinstance(usage, dict):
            return {}
        aliases = {"inputTokens": "input_tokens", "outputTokens": "output_tokens",
                   "cachedInputTokens": "cached_input_tokens", "totalTokens": "total_tokens",
                   "reasoningOutputTokens": "reasoning_output_tokens"}
        result = {}
        for key, value in usage.items():
            key = aliases.get(key, key)
            if key in {"input_tokens", "output_tokens", "cached_input_tokens", "total_tokens", "reasoning_output_tokens"} and type(value) is int and value >= 0:
                result[key] = value
        return result

    def _recompute_usage(self, run):
        calls = run.get("calls", [])
        fields = ("input_tokens", "output_tokens", "cached_input_tokens",
                  "total_tokens", "reasoning_output_tokens")
        totals = {key: 0 for key in fields}
        reported = 0
        missing = {key: False for key in fields}
        for call in calls:
            usage = call.get("usage")
            if not usage:
                continue
            reported += 1
            for key in fields:
                if type(usage.get(key)) is int:
                    totals[key] += usage[key]
                else:
                    missing[key] = True
        # A partial provider report must remain visibly unknown; never imply
        # that absent counters were zero.
        for key in fields:
            if reported == 0 or missing[key]:
                totals[key] = 0 if reported == 0 and not calls else None
        totals["reported_calls"] = reported
        totals["unreported_calls"] = max(0, run.get("progress", {}).get("model_calls", 0) - reported)
        run["usage"] = totals

    def begin_call(self, run_id, role, model, iteration, input_chars):
        with self._lock:
            run = self.get(run_id)
            call_id = uuid.uuid4().hex
            run.setdefault("calls", []).append({"call_id": call_id, "role": str(role)[:80],
                "model": str(model)[:120] if model is not None else None,
                "iteration": int(iteration) if type(iteration) is int else 0,
                "input_chars": max(0, int(input_chars)) if type(input_chars) is int else 0,
                "usage": None, "status": "running", "created_at": utc_now()})
            run.setdefault("progress", {})["model_calls"] = run.get("progress", {}).get("model_calls", 0) + 1
            self._recompute_usage(run)
            run["updated_at"] = utc_now()
            self._write(self._directory(run_id) / "run.json", run)
            return call_id

    def record_usage(self, run_id, call_id, usage, status=None):
        with self._lock:
            run = self.get(run_id)
            call = next((item for item in run.get("calls", []) if item.get("call_id") == call_id), None)
            if call is None:
                raise KeyError("Requested model call was not found.")
            cleaned = self._clean_usage(usage)
            if cleaned:
                call["usage"] = cleaned
            if status is not None:
                if str(status).lower() in {"completed", "failed", "stopped", "cancelled", "error", "budget_exhausted"}:
                    call.setdefault("completed_at", utc_now())
                    if "elapsed_seconds" not in call:
                        try:
                            started = datetime.fromisoformat(call["created_at"])
                            ended = datetime.fromisoformat(call["completed_at"])
                            call["elapsed_seconds"] = max(0.0, (ended - started).total_seconds())
                        except (KeyError, TypeError, ValueError):
                            call["elapsed_seconds"] = None
                call["status"] = str(status)[:40]
            self._recompute_usage(run)
            run["updated_at"] = utc_now()
            self._write(self._directory(run_id) / "run.json", run)
            return copy.deepcopy(run)

    def finish_call(self, run_id, call_id, status, usage=None):
        return self.record_usage(run_id, call_id, usage, status=status)

    def event(self, run_id, phase, message) -> dict:
        with self._lock:
            run = self.get(run_id)
            # Callers supply deliberately authored public messages, never exception details.
            run["events"].append({"at": utc_now(), "phase": str(phase)[:80], "message": str(message)[:500]})
            run["events"] = run["events"][-300:]
            run["phase"] = str(phase)[:80]
            run["updated_at"] = utc_now()
            self._write(self._directory(run_id) / "run.json", run)
            return copy.deepcopy(run)

    def add_snapshot(self, run_id, snapshot) -> dict:
        with self._lock:
            run = self.get(run_id)
            value = copy.deepcopy(snapshot)
            value.setdefault("id", uuid.uuid4().hex)
            value.setdefault("created_at", utc_now())
            snapshot_id = safe_id(value["id"])
            path = self._directory(run_id) / "snapshots" / f"{snapshot_id}.json"
            if path.exists():
                raise ValueError("Snapshots are immutable; this identifier already exists.")
            self._write(path, value)
            metrics = value.get("metrics", {})
            run["snapshots"].append({
                "id": snapshot_id, "iteration": value["iteration"],
                "created_at": value["created_at"], "depth": metrics.get("depth", 0),
                "node_count": len(value.get("nodes", [])), "edge_count": len(value.get("edges", [])),
            })
            run["latest_snapshot"] = value
            run["iteration"] = value["iteration"]
            run["progress"]["included"] = len(value.get("nodes", []))
            run["updated_at"] = utc_now()
            self._write(self._directory(run_id) / "run.json", run)
            return copy.deepcopy(value)

    def snapshot(self, run_id, snapshot_id) -> dict:
        with self._lock:
            self.get(run_id)
            folder = self._directory(run_id) / "snapshots"
            path = folder / f"{safe_id(snapshot_id)}.json"
            if path.resolve().parent != folder.resolve():
                raise ValueError("Snapshot path must stay inside its storage directory.")
            return self._load(path)

    def resume(self, run_id, snapshot_id, config=None) -> dict:
        with self._lock:
            original = self.get(run_id)
            selected = self.snapshot(run_id, snapshot_id)
            branch_config = copy.deepcopy(original["config"] if config is None else config)
            branch = self.create(original["seed"], branch_config, original["mode"],
                                 {"run_id": run_id, "snapshot_id": snapshot_id})
            self.add_snapshot(branch["id"], selected)
            self.event(branch["id"], "queued", "Created an independent branch from the selected snapshot.")
            return self.get(branch["id"])

    def synthesis_budget(self, run_id):
        """Count recovery ancestors once, including legacy branches with reset caps."""
        with self._lock:
            current = self.get(run_id)
            calls, seconds, seen = 0, 0.0, set()
            while True:
                if current["id"] in seen:
                    raise ValueError("Cannot establish the original exploration budget.")
                seen.add(current["id"])
                progress = current.get("progress", {})
                calls += max(progress.get("model_calls", 0), len(current.get("calls", [])))
                call_seconds = sum(c.get("elapsed_seconds") or 0 for c in current.get("calls", []))
                seconds += max(progress.get("elapsed_seconds", 0), call_seconds)
                carried = current.get("budget_carry")
                if carried:
                    calls += carried["model_calls"]
                    seconds += carried["elapsed_seconds"]
                    root_id = carried["root_run_id"]
                    iteration_limit = carried["iteration_limit"]
                    break
                parent = current.get("parent") or {}
                if parent.get("recovery") != "synthesis":
                    root_id = current["id"]
                    start = next((s["iteration"] for s in current.get("snapshots", [])
                                  if s["id"] == parent.get("snapshot_id")), 0)
                    if parent.get("reanalysis"):
                        # The new budget covers one fixed-corpus pass at the
                        # source draft's iteration number, including later retries.
                        draft = self.working(current["id"]).get("synthesis_draft") or {}
                        iteration_limit = max(1, int(draft.get("iteration") or 1))
                    else:
                        iteration_limit = start + current["config"]["max_iterations"]
                    break
                current = self.get(parent["run_id"])
            limits = copy.deepcopy(current["config"])
            return {"root_run_id": root_id, "limits": limits, "iteration_limit": iteration_limit,
                    "model_calls_used": calls, "elapsed_seconds_used": round(seconds, 1),
                    "remaining_model_calls": max(0, limits["max_model_calls"] - calls),
                    "remaining_seconds": max(0, limits["max_seconds"] - seconds)}

    def synthesis_successor(self, run_id):
        """A recovery continues a single lineage; old checkpoints cannot mint budget."""
        with self._lock:
            run = self.get(run_id)
            if run.get("recovery_child_id"):
                return run["recovery_child_id"]
            # Legacy records predate the durable successor pointer. Include trash
            # so moving a recovery out of the sidebar cannot reset its budget.
            for folder in (self._runs, self._trash):
                for path in folder.glob("*/run.json"):
                    child = self._load(path)
                    parent = child.get("parent") or {}
                    if parent.get("recovery") == "synthesis" and parent.get("run_id") == run_id:
                        return child["id"]
            return None

    def reanalyze(self, run_id, config):
        """Create a fresh-budget synthesis branch over the original readable sources."""
        if config is None:
            raise ValueError("A fresh run configuration is required.")
        with self._lock:
            original = self.get(run_id)
            if original["status"] in {"running", "queued", "stopping"}:
                raise ValueError("Stop the active exploration before reanalyzing it.")
            working = self.working(run_id)
            papers = working.get("papers")
            read_ids = working.get("read_ids")
            if not isinstance(papers, dict) or not papers or not isinstance(read_ids, list) or not read_ids:
                raise ValueError("No readable cached sources are available for reanalysis.")
            read_ids = list(dict.fromkeys(str(paper_id) for paper_id in read_ids))
            if any(paper_id not in papers or not isinstance(papers[paper_id], dict) for paper_id in read_ids):
                raise ValueError("Cached sources do not match the recorded read set.")
            for paper_id in read_ids:
                paper = papers[paper_id]
                if paper.get("id") != paper_id or not (paper.get("abstract") or any(
                        isinstance(row, dict) and row.get("text") and row.get("kind") != "metadata_affiliation"
                        for row in paper.get("passages", []))):
                    raise ValueError("Reanalysis requires readable, identity-matched cached sources.")
            draft = working.get("synthesis_draft")
            latest = original.get("latest_snapshot")
            selected = draft if isinstance(draft, dict) and draft.get("seed_id") else latest
            if not isinstance(selected, dict) or not selected.get("seed_id"):
                raise ValueError("Reanalysis requires a saved draft or snapshot containing the seed.")
            seed_id = str(selected["seed_id"])
            if seed_id not in read_ids or seed_id not in papers:
                raise ValueError("The saved seed is not present in the readable source set.")
            branch = self.create(original["seed"], config, original["mode"],
                                {"run_id": run_id, "snapshot_id": selected.get("id"),
                                 "reanalysis": True, "draft_id": draft.get("id") if isinstance(draft, dict) else None})
            cloned_working = {
                "papers": {paper_id: copy.deepcopy(papers[paper_id]) for paper_id in read_ids},
                "read_ids": list(read_ids),
                "discovery": copy.deepcopy(working.get("discovery") or (selected.get("discovery") or {})),
                "synthesis_draft": copy.deepcopy(selected),
                "refinement": {},
                "reanalyze_existing": True,
                "retry_synthesis_only": True,
                "fixed_corpus": True,
                "exploration": copy.deepcopy(working.get("exploration", {})),
            }
            # This branch has no unread candidate frontier.
            cloned_working["discovery"]["pending_candidates"] = []
            self.working(branch["id"], cloned_working)
            self.event(branch["id"], "queued", "Created an independent reanalysis branch from cached readable sources.")
            return self.get(branch["id"])

    def retry_synthesis(self, run_id):
        """Continue saved analysis with the original exploration's remaining budget."""
        with self._lock:
            original = self.get(run_id)
            if original["status"] in {"running", "queued", "stopping"}:
                raise ValueError("Stop the active exploration before retrying its synthesis.")
            working = self.working(run_id)
            draft = working.get("synthesis_draft")
            if not draft or draft.get("completion_status") != "incomplete":
                raise ValueError("No unfinished synthesis is available to continue.")
            if self.synthesis_successor(run_id):
                raise ValueError("This analysis has already been continued. Resume its latest continuation instead.")
            budget = self.synthesis_budget(run_id)
            if budget["remaining_model_calls"] <= 0 or budget["remaining_seconds"] <= 0:
                raise ValueError("The original exploration budget is exhausted.")
            last = original.get("latest_snapshot")
            branch = self.create(original["seed"], budget["limits"], original["mode"],
                {"run_id": run_id, "snapshot_id": last["id"] if last else None,
                 "recovery": "synthesis", "draft_id": draft["id"]})
            self.update(branch["id"], budget_carry={"root_run_id": budget["root_run_id"],
                "model_calls": budget["model_calls_used"], "elapsed_seconds": budget["elapsed_seconds_used"],
                "iteration_limit": budget["iteration_limit"]})
            if last:
                self.add_snapshot(branch["id"], last)
            working["retry_synthesis_only"] = True
            self.working(branch["id"], working)
            self.update(run_id, recovery_child_id=branch["id"])
            self.event(branch["id"], "queued", "Resuming saved analysis within the original exploration budget; synthesis revisions continue automatically.")
            return self.get(branch["id"])

    def save_synthesis_attempt(self, run_id, snapshot, role, attempt):
        """Keep each normalized model result even when it is not a completed iteration."""
        with self._lock:
            run = self.get(run_id)
            path = self._directory(run_id) / "analysis" / (safe_id(snapshot["id"]) + ".json")
            if path.exists():
                return
            self._write(path, copy.deepcopy(snapshot))
            run.setdefault("synthesis_attempts", []).append({
                "id": snapshot["id"], "iteration": snapshot["iteration"],
                "role": role, "attempt": attempt, "created_at": utc_now(),
                "node_count": len(snapshot.get("nodes", [])),
                "quality": copy.deepcopy(snapshot.get("synthesis_quality", {})),
                "refinement": copy.deepcopy(snapshot.get("refinement", {}))})
            self._write(self._directory(run_id) / "run.json", run)

    def recover_interrupted(self) -> int:
        count = 0
        with self._lock:
            for run in self.list_runs():
                if run["status"] in {"running", "queued", "stopping"}:
                    self.update(run["id"], status="interrupted", phase="interrupted",
                                stop_reason="The local application restarted. Resume a saved snapshot to continue.")
                    count += 1
        return count

    def working(self, run_id, value=None) -> dict:
        """Private extraction cache; not part of exported snapshots or public run JSON."""
        with self._lock:
            self.get(run_id)
            path = self._directory(run_id) / "working.json"
            if value is not None:
                self._write(path, copy.deepcopy(value))
            return self._load(path) if path.exists() else {}
