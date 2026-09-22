"""Small, model-free helpers for turning synthesis failures into reading tasks.

The engine owns discovery and quota accounting.  This module only decides what
evidence is worth looking at next, and deliberately accepts the loose records
used by old snapshots and literature providers.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable


_WORD = re.compile(r"[\w]+", re.UNICODE)


def _tokens(value) -> set[str]:
    return {x.lower() for x in _WORD.findall(str(value or "")) if len(x) > 1}


def _paper_map(papers) -> dict[str, dict]:
    if isinstance(papers, dict):
        return {str(k): v for k, v in papers.items() if isinstance(v, dict)}
    return {str(p.get("id")): p for p in (papers or []) if isinstance(p, dict) and p.get("id") is not None}


def _task_id(kind, ids, question):
    raw = kind + "|" + ",".join(sorted(map(str, ids))) + "|" + question
    return "evidence:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _task(kind, ids, question, terms, reason):
    ids = list(dict.fromkeys(str(x) for x in ids if x is not None))
    return {"id": _task_id(kind, ids, question), "kind": kind, "paper_ids": ids,
            "question": question, "terms": sorted(set(terms)), "reason": reason}


def plan_evidence_tasks(snapshot, papers, required_ids) -> list[dict]:
    """Create bounded, actionable tasks while retaining every required source.

    A singleton is a consolidation task, rather than a failure: it asks the
    reader to find a defensible place for that source in the mainline.
    """
    snapshot = snapshot or {}
    pmap = _paper_map(papers)
    required = [str(x) for x in (required_ids or []) if str(x) in pmap]
    nodes = {str(n.get("id")): n for n in snapshot.get("nodes", []) if isinstance(n, dict) and n.get("id") is not None}
    edges = [e for e in snapshot.get("edges", []) + snapshot.get("comparisons", []) if isinstance(e, dict)]
    tasks, seen = [], set()

    for gap in snapshot.get("gaps", []) or []:
        if not isinstance(gap, dict):
            continue
        ids = [str(x) for x in gap.get("paper_ids", []) if str(x) in pmap]
        if not ids:
            continue
        kind = "bridge" if len(ids) >= 2 else "source"
        ids = ids[:2]
        question = str(gap.get("description") or gap.get("question") or "What evidence establishes this missing relation?")
        terms = _tokens(question + " " + " ".join(pmap[x].get("title", "") for x in ids))
        item = _task(kind, ids, question, terms, "snapshot gap")
        if item["id"] not in seen:
            tasks.append(item); seen.add(item["id"])

    invalid = [e for e in edges if e.get("status") in {"rejected", "hypothesis"}]
    for edge in invalid:
        ids = [str(edge.get("source")), str(edge.get("target"))]
        ids = [x for x in ids if x in pmap]
        if len(ids) != 2:
            continue
        question = str(edge.get("rationale") or edge.get("problem") or "Which evidence supports the proposed transition and its direction?")
        terms = _tokens(question + " " + str(edge.get("mechanism", "")))
        item = _task("bridge", ids, question, terms, "invalid or unverified transition")
        if item["id"] not in seen:
            tasks.append(item); seen.add(item["id"])

    valid_progressions = {(str(e.get("source")), str(e.get("target"))) for e in edges
                          if e.get("status") == "supported" and e.get("kind") in {"addresses", "builds_on", "challenges"}}
    failed_spine_other = {}
    for group in snapshot.get("groups", []) or []:
        if not isinstance(group, dict) or not isinstance(group.get("spine"), list):
            continue
        for step in group["spine"]:
            if not isinstance(step, dict):
                continue
            source, target = str(step.get("source")), str(step.get("target"))
            if source not in pmap or target not in pmap or (source, target) in valid_progressions:
                continue
            claim = str(step.get("claim_connection") or "the claimed technical transition")
            question = f"Verify the missing supported transition {source} -> {target}: {claim}. Which evidence establishes the mechanism and direction?"
            item = _task("bridge", [source, target], question, _tokens(question), "group spine transition lacks a supported edge")
            if item["id"] not in seen:
                tasks.append(item); seen.add(item["id"])
            failed_spine_other.setdefault(source, []).append(target)
            failed_spine_other.setdefault(target, []).append(source)
    explained = set()
    for e in edges:
        if e.get("status") == "supported":
            explained.update((str(e.get("source")), str(e.get("target"))))
    for group in snapshot.get("groups", []) or []:
        for support in group.get("member_support", []) if isinstance(group, dict) else []:
            if support.get("evidence_ids"):
                explained.add(str(support.get("paper_id")))
    quality = snapshot.get("synthesis_quality", {}) or {}
    unexplained = set(map(str, quality.get("unconnected_source_ids", []) or []))
    unexplained.update(map(str, quality.get("missing_source_ids", []) or []))
    unexplained.update(str(x) for d in quality.get("group_diagnostics", []) or [] for x in d.get("unexplained_member_ids", []) or [])
    unexplained.update(x for x in required if x not in explained and x != str(snapshot.get("seed_id")))
    for pid in sorted(unexplained):
        if pid not in pmap:
            continue
        related = list(failed_spine_other.get(pid, []))
        for edge in edges:
            ends = [str(edge.get("source")), str(edge.get("target"))]
            if pid in ends:
                other = ends[1] if ends[0] == pid else ends[0]
                if other in pmap and other != pid: related.append(other)
        for group in snapshot.get("groups", []) or []:
            members = [str(x) for x in (group.get("member_ids", []) if isinstance(group, dict) else [])]
            members += [str(x.get("paper_id")) for x in (group.get("member_support", []) if isinstance(group, dict) else []) if isinstance(x, dict)]
            if pid in members:
                related.extend(x for x in members if x in pmap and x != pid)
        related = list(dict.fromkeys(related))
        ids = [pid] + related[:1]
        question = ("How does this work connect to the adjacent source's technical problem, mechanism, or limitation?"
                    if related else "What source-grounded role does this work play, if any, in the current explanation?")
        terms = _tokens(question + " " + pmap[pid].get("title", ""))
        item = _task("merge" if related else "source", ids, question, terms, "required source is unexplained")
        if item["id"] not in seen:
            tasks.append(item); seen.add(item["id"])
    return tasks


def targeted_packets(papers, task, max_chars=20000, seen_passage_ids=None) -> list[dict]:
    """Return fair, task-focused packets without cutting complete passages."""
    pmap = _paper_map(papers); task = task or {}
    ids = list(dict.fromkeys(str(x) for x in task.get("paper_ids", []) if str(x) in pmap))
    terms = _tokens(" ".join(map(str, task.get("terms", []))) + " " + task.get("question", ""))
    seen = set(seen_passage_ids or [])
    eligible = {}
    for pid in ids:
        rows = [p for p in pmap[pid].get("passages", []) if isinstance(p, dict) and isinstance(p.get("text"), str)
                and p.get("kind") != "metadata_affiliation" and "metadata" not in str(p.get("location", "")).lower()]
        ranked = []
        for i, p in enumerate(rows):
            relevance = len(terms & _tokens(p.get("text"))) + (2 if "abstract" in str(p.get("location", "")).lower() else 0)
            ranked.append((relevance, p.get("id") in seen, i, rows))
        eligible[pid] = sorted(ranked, key=lambda x: (-x[0], x[1], x[2]))
    budget = max(0, int(max_chars))
    selected = {pid: [] for pid in ids}; selected_keys = set(); used = 0
    # First give every endpoint its best complete passage that fits.
    for pid in ids:
        for relevance, already_seen, i, rows in eligible[pid]:
            text_len = len(rows[i].get("text", ""))
            if text_len <= budget - used:
                selected[pid].append(rows[i]); selected_keys.add((pid, i)); used += text_len
                break
    # Then round-robin relevant passages and adjacent context.
    changed = True
    while changed:
        changed = False
        for pid in ids:
            for relevance, already_seen, i, rows in eligible[pid]:
                options = [i - 1, i + 1, i]
                for j in options:
                    if j < 0 or j >= len(rows) or (pid, j) in selected_keys: continue
                    text_len = len(rows[j].get("text", ""))
                    if text_len <= budget - used:
                        selected[pid].append(rows[j]); selected_keys.add((pid, j)); used += text_len; changed = True
                        break
                if changed: break
    packets = []
    for pid in ids:
        paper = pmap[pid]
        packet = {k: paper.get(k) for k in ("id", "title", "date", "year", "source_status", "context_role", "context_reason", "context_for", "context_problem", "citation_links")}
        packet["is_new"] = False
        packet["passages"] = selected[pid]
        if not selected[pid]:
            packet["source_gap"] = "No complete passage from this endpoint fits the remaining evidence budget."
        packets.append(packet)
    return packets
def survey_packets(papers, max_chars=70000) -> list[dict]:
    """Build a balanced first-read overview from complete source passages.

    The caller may replace ``is_new`` after discovery.  This function never
    fetches or truncates text: a passage is either included in full or omitted.
    """
    pmap = _paper_map(papers)
    ids = list(pmap)
    budget = max(0, int(max_chars))
    per_source = budget // max(1, len(ids))
    section_terms = {
        "abstract": ("abstract",),
        "own_method": ("method", "approach", "model", "framework", "algorithm", "we propose", "our method"),
        "evaluation": ("evaluation", "experiment", "benchmark", "baseline", "ablation", "protocol", "dataset", "results"),
        "limitations": ("limitation", "failure", "future work", "does not", "threat"),
        "related_work": ("related work", "prior work", "background", "previous work"),
    }
    packets = []
    for pid, paper in pmap.items():
        rows = [p for p in paper.get("passages", []) if isinstance(p, dict) and isinstance(p.get("text"), str)
                and p.get("kind") != "metadata_affiliation" and "metadata" not in str(p.get("location", "")).lower()]
        coverage = {key: [] for key in section_terms}
        selected, used, selected_ids = [], 0, set()
        scored = []
        for index, passage in enumerate(rows):
            haystack = (str(passage.get("location", "")) + " " + passage.get("text", "")).lower()
            matched = [section for section, terms in section_terms.items() if any(term in haystack for term in terms)]
            scored.append((index, matched))
        # One complete passage per section first, in the requested reading order.
        for section in section_terms:
            for index, matched in scored:
                if section not in matched or index in selected_ids:
                    continue
                length = len(rows[index]["text"])
                if length <= per_source - used:
                    selected.append(rows[index]); selected_ids.add(index); used += length; coverage[section].append(rows[index].get("id"))
                    break
        # Fill remaining source quota in document order, preserving complete passages.
        for index, matched in scored:
            if index in selected_ids:
                continue
            length = len(rows[index]["text"])
            if length <= per_source - used:
                selected.append(rows[index]); selected_ids.add(index); used += length
                for section in matched:
                    coverage[section].append(rows[index].get("id"))
        gaps = [section for section, passage_ids in coverage.items() if not passage_ids]
        packet = {k: paper.get(k) for k in ("id", "title", "date", "year", "source_status", "context_role", "context_reason", "context_for", "context_problem", "citation_links")}
        packet["is_new"] = False
        packet["passages"] = selected
        packet["section_coverage"] = coverage
        if gaps:
            packet["source_gap"] = gaps
        packets.append(packet)
    return packets
def candidate_bridges(task, papers, read_ids, eligible_ids, limit=3) -> list[str]:
    """Rank only caller-approved direct-citation candidates."""
    pmap = _paper_map(papers); read = set(map(str, read_ids or [])); eligible = [str(x) for x in eligible_ids or []]
    terms = _tokens(" ".join(map(str, (task or {}).get("terms", []))) + " " + (task or {}).get("question", ""))
    scored = []
    for pid in eligible:
        if pid in read or pid not in pmap: continue
        paper = pmap[pid]; text = paper.get("title", "") + " " + paper.get("abstract", "") + " " + " ".join(p.get("text", "") for p in paper.get("passages", []) if isinstance(p, dict))
        scored.append((len(terms & _tokens(text)), pid))
    return [pid for _, pid in sorted(scored, key=lambda x: (-x[0], x[1]))[:max(0, int(limit))]]
