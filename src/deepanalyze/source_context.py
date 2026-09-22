"""Bounded, source-provenance context for semantic review."""

from __future__ import annotations

import hashlib


def _norm(value):
    return " ".join(str(value or "").split())


def _passages(paper):
    return [item for item in paper.get("passages", []) if isinstance(item, dict) and isinstance(item.get("text"), str) and item.get("text").strip()]


def _ref_ids(snapshot, paper_id):
    node = next((item for item in snapshot.get("nodes", []) if isinstance(item, dict) and item.get("id") == paper_id), {})
    assessment = node.get("research_assessment") if isinstance(node.get("research_assessment"), dict) else {}
    prioritized = list(assessment.get("evidence_ids", [])) if isinstance(assessment.get("evidence_ids"), list) else []
    others = []
    for group in snapshot.get("groups", []) if isinstance(snapshot.get("groups"), list) else []:
        for record in group.get("member_support", []) if isinstance(group, dict) and isinstance(group.get("member_support"), list) else []:
            if not isinstance(record, dict) or record.get("paper_id") != paper_id:
                continue
            for field in ("evidence_ids", "attachment_evidence_ids"):
                if isinstance(record.get(field), list):
                    others.extend(record[field])
    for edge in snapshot.get("edges", []) if isinstance(snapshot.get("edges"), list) else []:
        if not isinstance(edge, dict) or paper_id not in {edge.get("source"), edge.get("target")}:
            continue
        if isinstance(edge.get("evidence_ids"), list):
            others.extend(edge["evidence_ids"])
    return list(dict.fromkeys([ref for ref in prioritized + others if isinstance(ref, str) and ref]))


def _evidence_map(node):
    return {item.get("id"): item for item in node.get("evidence", []) if isinstance(item, dict) and item.get("verified") is True and item.get("id")}


def _render(paper_id, paper, passage):
    return {"id": passage.get("id") or f"{paper_id}:passage:{hashlib.sha256(passage.get('text', '').encode()).hexdigest()[:16]}",
            "text": passage.get("text", ""), "location": passage.get("location", ""),
            "source_paper_id": paper_id, "source_title": paper.get("title", ""),
            "source_url": paper.get("url", ""), "kind": passage.get("kind", "passage")}


def review_source_context(snapshot, papers, max_chars_per_paper=6500):
    """Return bounded whole-passage context keyed by paper ID."""
    papers = papers or {}
    result = {}
    for paper_id, paper in papers.items():
        if not isinstance(paper, dict):
            result[str(paper_id)] = []
            continue
        paper_id = str(paper_id)
        node = next((item for item in snapshot.get("nodes", []) if isinstance(item, dict) and item.get("id") == paper_id), {})
        evidence = _evidence_map(node)
        passages = _passages(paper)
        refs = _ref_ids(snapshot, paper_id)
        selected = []
        selected_indices = set()
        for ref in refs:
            item = evidence.get(ref)
            if not item:
                continue
            quote = _norm(item.get("quote"))
            location = _norm(item.get("location"))
            index = next((i for i, passage in enumerate(passages) if quote and quote in _norm(passage.get("text"))), None)
            if index is None and location:
                index = next((i for i, passage in enumerate(passages) if _norm(passage.get("id")) == location or _norm(passage.get("location")) == location), None)
            if index is None:
                continue
            selected.append((index, 0))
            for distance in (1, 2):
                if index - distance >= 0:
                    selected.append((index - distance, distance))
                if index + distance < len(passages):
                    selected.append((index + distance, distance))
        # Assessment anchors come first; neighboring passages are added by distance.
        chosen = []
        for index, distance in sorted(selected, key=lambda value: (0 if value[1] == 0 else 1, value[1], value[0])):
            if index in selected_indices:
                continue
            rendered = _render(paper_id, paper, passages[index])
            if len(rendered["text"]) > max_chars_per_paper:
                continue
            used = sum(len(item["text"]) for item in chosen)
            if used + len(rendered["text"]) > max_chars_per_paper:
                continue
            selected_indices.add(index)
            chosen.append(rendered)
        result[paper_id] = sorted(chosen, key=lambda item: next((i for i, p in enumerate(passages) if (p.get("id") or f"{paper_id}:passage:{hashlib.sha256(p.get('text', '').encode()).hexdigest()[:16]}") == item["id"]), 0))
    return result
