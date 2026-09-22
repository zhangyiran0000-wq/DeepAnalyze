"""Structural checks for proposed explanatory groups.

This module checks explicit claims, source attribution and the shape of a proposed
spine. It does not establish that quotations entail a claim or that a mechanism
is scientifically correct. Inputs should be normalized snapshot records.
"""

from __future__ import annotations

from collections import deque
import re


_PROGRESSION = {"addresses", "builds_on"}
_CLAIM_FIELDS = ("constraint", "mechanism", "consequence")


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _records(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _ids(value):
    return [_text(item) for item in value if _text(item)] if isinstance(value, list) else []



def _multiple_targets(concept):
    """Reject explicit top-level lists, not every phrase containing several nouns.

    This is a conservative syntax check, not semantic proof of a single target.
    Relation arguments (``between`` / ``\u4e4b\u95f4``) and bracketed parameters can
    contain comma-separated nouns without naming several independent objectives.
    """
    if re.search(r"[;\uff1b\r\n]", concept):
        return True
    english_relation = re.search(r"\bbetween\b", concept, flags=re.IGNORECASE)
    chinese_relation = concept.find("\u4e4b\u95f4")
    closing = []
    brackets = {"(": ")", "[": "]", "{": "}", "\uff08": "\uff09", "\u3010": "\u3011"}
    for index, char in enumerate(concept):
        if char in brackets:
            closing.append(brackets[char])
        elif closing and char == closing[-1]:
            closing.pop()
        elif char in ",\uff0c\u3001" and not closing:
            if english_relation and index >= english_relation.end():
                continue
            if chinese_relation >= 0 and index < chinese_relation:
                continue
            if (char == "," and index > 0 and index + 1 < len(concept)
                    and concept[index - 1].isdigit() and concept[index + 1].isdigit()):
                continue
            return True
    return False


def _attributed(refs, owners, expected):
    """All references must be verified and collectively belong to exactly these sources."""
    if not isinstance(refs, list) or not refs:
        return False
    if any(not _text(ref) or ref not in owners for ref in refs):
        return False
    return {owners[ref] for ref in refs} == expected


def _supported(edge, owners, kinds):
    source, target = _text(edge.get("source")), _text(edge.get("target"))
    return (
        source and target and source != target
        and edge.get("status") == "supported" and edge.get("kind") in kinds
        and _text(edge.get("problem")) and _text(edge.get("mechanism"))
        and _attributed(edge.get("evidence_ids"), owners, {source, target})
    )


def _spine_shape(pairs):
    """Return weak connectivity, acyclicity and longest directed path length."""
    vertices = {key for pair in pairs for key in pair}
    if not vertices:
        return False, True, 0
    neighbors = {key: set() for key in vertices}
    children = {key: set() for key in vertices}
    incoming = dict.fromkeys(vertices, 0)
    for source, target in pairs:
        neighbors[source].add(target)
        neighbors[target].add(source)
        children[source].add(target)
        incoming[target] += 1
    reached, pending = set(), [next(iter(vertices))]
    while pending:
        current = pending.pop()
        if current not in reached:
            reached.add(current)
            pending.extend(neighbors[current] - reached)
    queue = deque(key for key in vertices if incoming[key] == 0)
    lengths = dict.fromkeys(vertices, 0)
    visited = 0
    while queue:
        source = queue.popleft()
        visited += 1
        for target in children[source]:
            lengths[target] = max(lengths[target], lengths[source] + 1)
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    acyclic = visited == len(vertices)
    return reached == vertices, acyclic, max(lengths.values(), default=0) if acyclic else 0


def _publication_order(paper_id, node_map):
    """Known years precede unknown years; identity gives a deterministic tie-break."""
    try:
        year = int(node_map[paper_id].get("year"))
    except (TypeError, ValueError):
        year = 0
    return (year if year > 0 else float("inf"), paper_id)


def evaluate_groups(groups, nodes, edges, comparisons):
    """Return one nonmutating, evidence-attribution diagnostic per proposed group.

    Actual membership comes from normalized ``nodes[*].group_ids``. A group has
    one core target phrase; ``label_nouns`` counts declared entries, not parsed
    language-dependent nouns. Incomplete diagnostics describe working drafts,
    never a completed synthesis. The one-source bootstrap and directly grounded
    parallel alternatives can have depth zero without inventing progression.
    Branches attach directly to the spine: complementary relations or a chain of
    alternatives cannot silently turn unrelated material into explained coverage.
    """
    node_map = {_text(node.get("id")): node for node in _records(nodes) if _text(node.get("id"))}
    owners = {}
    ambiguous = set()
    for paper_id, node in node_map.items():
        for evidence in _records(node.get("evidence")):
            ref = _text(evidence.get("id"))
            if not ref or evidence.get("verified") is not True:
                continue
            if ref in owners and owners[ref] != paper_id:
                ambiguous.add(ref)
            else:
                owners[ref] = paper_id
    for ref in ambiguous:
        owners.pop(ref, None)
    progressions = {
        (_text(edge.get("source")), _text(edge.get("target")))
        for edge in _records(edges) if _supported(edge, owners, _PROGRESSION)
    }
    attachments = set()
    for edge in _records(edges):
        if _supported(edge, owners, {"challenges"}):
            attachments.add(frozenset((_text(edge.get("source")), _text(edge.get("target")))))
    for comparison in _records(comparisons):
        source, target = _text(comparison.get("source")), _text(comparison.get("target"))
        if (source and target and source != target and comparison.get("grounded") is True
                and comparison.get("relation") == "alternative"
                and _text(comparison.get("shared_problem"))
                and _attributed(comparison.get("evidence_ids"), owners, {source, target})):
            attachments.add(frozenset((source, target)))

    results = []
    group_records = _records(groups)
    for group in group_records:
        group_id = _text(group.get("id"))
        members = {key for key, node in node_map.items() if group_id in _ids(node.get("group_ids"))}
        issues = []
        warnings = []

        def issue(code):
            if code not in issues:
                issues.append(code)

        concept = _text(group.get("core_concept"))
        if not concept:
            issue("missing_core_concept")
        elif _multiple_targets(concept):
            issue("multiple_core_targets")
        label_nouns = group.get("label_nouns")
        if not isinstance(label_nouns, list) or not label_nouns:
            issue("missing_label_nouns")
        else:
            if len(label_nouns) > 5:
                issue("label_noun_limit_exceeded")
            cleaned = [_text(value) for value in label_nouns]
            if not all(cleaned):
                issue("invalid_label_nouns")
            if len({value.casefold() for value in cleaned}) != len(cleaned):
                issue("duplicate_label_nouns")
        claim = group.get("explanatory_claim")
        claim_complete = isinstance(claim, dict) and all(_text(claim.get(key)) for key in _CLAIM_FIELDS)
        if not claim_complete:
            issue("incomplete_explanatory_claim")
        bootstrap = len(node_map) == 1 and len(group_records) == 1 and len(members) == 1
        if not members:
            issue("empty_group")
        elif len(members) == 1 and not bootstrap:
            warnings.append("singleton_group")

        if group.get("explanation_model") == "knowledge_transitions_v1":
            results.append(_knowledge_group(group, node_map, owners, edges, claim_complete, issues, warnings))
            continue

        support = set()
        records = _records(group.get("member_support"))
        if not records:
            issue("missing_member_support")
        for record in records:
            paper_id = _text(record.get("paper_id"))
            if paper_id not in members or not _text(record.get("claim_connection")):
                issue("invalid_member_support")
            elif not _attributed(record.get("evidence_ids"), owners, {paper_id}):
                issue("invalid_member_evidence")
            else:
                support.add(paper_id)
        if members - support:
            issue("missing_member_support")

        pairs = set()
        raw_spine = group.get("spine")
        if isinstance(raw_spine, list):
            for step in raw_spine:
                if not isinstance(step, dict):
                    issue("invalid_spine_transition")
                    continue
                source, target = _text(step.get("source")), _text(step.get("target"))
                if (source not in members or target not in members or source == target
                        or not _text(step.get("claim_connection"))
                        or (source, target) not in progressions):
                    issue("invalid_spine_transition")
                else:
                    pairs.add((source, target))
        elif raw_spine is not None:
            issue("invalid_spine_transition")
        connected, acyclic, depth = _spine_shape(pairs)
        if not acyclic:
            issue("cyclic_spine")
        # Parallel tracks can join through reviewed alternatives or challenges;
        # requiring every branch to attach directly to one root invents a shape.
        neighbors = {key: set() for key in members}
        for source, target in pairs:
            neighbors[source].add(target)
            neighbors[target].add(source)
        for pair in attachments:
            if pair <= members:
                source, target = tuple(pair)
                neighbors[source].add(target)
                neighbors[target].add(source)
        eligible = set()
        if members and acyclic:
            root = min(members, key=lambda key: _publication_order(key, node_map))
            pending = [root]
            while pending:
                key = pending.pop()
                if key not in eligible:
                    eligible.add(key)
                    pending.extend(neighbors[key] - eligible)
        if pairs and eligible != members:
            issue("disconnected_spine")
        if len(members) >= 2 and not pairs and not any(neighbors.values()):
            issue("missing_spine")
            eligible = set()
        if len(members) == 1:
            eligible = set(members)
        covered = members & support & eligible if claim_complete else set()
        unexplained = members - covered
        if unexplained:
            issue("unexplained_members")
        results.append({
            "group_id": group_id,
            "status": "evidence_linked" if not issues and members else "incomplete",
            "spine_depth": depth,
            "covered_member_ids": sorted(covered),
            "unexplained_member_ids": sorted(unexplained),
            "issues": issues, "warnings": warnings,
        })
    return results


_KNOWLEDGE_ROLES = {"advance", "revision", "proposal", "incremental", "replication", "tooling"}
_OUTCOMES = {"demonstrated", "partial", "not_tested", "contradicted", "unknown"}


def _knowledge_group(group, nodes, owners, edges, claim_complete, issues, warnings):
    """Check a stage account without making every retained paper a turning point."""
    group_id = group["id"]
    members = {key for key, node in nodes.items() if group_id in _ids(node.get("group_ids"))}
    issues = list(issues)
    def issue(code):
        if code not in issues:
            issues.append(code)
    records = {}
    support = set()
    for record in _records(group.get("member_support")):
        key = _text(record.get("paper_id"))
        if key in records:
            issue("duplicate_member_support")
        records[key] = record
        if key not in members or not _text(record.get("claim_connection")):
            issue("invalid_member_support")
            continue
        if not _attributed(record.get("evidence_ids"), owners, {key}):
            issue("invalid_member_evidence")
            continue
        if (record.get("role") not in _KNOWLEDGE_ROLES or not _text(record.get("knowledge_change"))
                or not _text(record.get("removal_effect"))):
            issue("missing_research_role")
            continue
        assessment = nodes[key].get("research_assessment") or {}
        if (assessment.get("outcome") not in _OUTCOMES or not _text(assessment.get("claimed_problem"))
                or (assessment.get("outcome") in {"demonstrated", "partial", "contradicted"}
                    and not all(_text(assessment.get(field)) for field in ("demonstrated_result", "conditions")))
                or not _attributed(assessment.get("evidence_ids"), owners, {key})):
            issue("missing_research_assessment")
            continue
        support.add(key)
    if members - records.keys():
        issue("missing_member_support")
    root = _text(group.get("root_id"))
    if root not in members:
        issue("invalid_stage_root")
    candidates = {(e.get("source"), e.get("target")) for e in _records(edges)
                  if _supported(e, owners, {"addresses", "builds_on", "challenges"})}
    pairs, statements = set(), set()
    for step in _records(group.get("spine")):
        a, b = _text(step.get("source")), _text(step.get("target"))
        before, after = _text(step.get("before")), _text(step.get("after"))
        signature = (" ".join(before.casefold().split()), " ".join(after.casefold().split()))
        if (a not in members or b not in members or a == b or (a, b) not in candidates
                or not _text(step.get("claim_connection"))):
            issue("invalid_spine_transition")
            continue
        if (not before or not after or signature[0] == signature[1]
                or step.get("transition_type") not in {"advance", "revision", "reframing"}):
            issue("missing_knowledge_transition")
            continue
        if signature in statements:
            issue("redundant_knowledge_transition")
            continue
        if records.get(b, {}).get("role") in {"incremental", "replication"}:
            issue("incremental_work_on_spine")
            continue
        statements.add(signature)
        pairs.add((a, b))
    if not isinstance(group.get("spine"), list) or any(not isinstance(step, dict) for step in group.get("spine", [])):
        issue("invalid_spine_transition")
    _, acyclic, depth = _spine_shape(pairs)
    if not acyclic:
        issue("cyclic_spine")
    children = {key: set() for key in members}
    for a, b in pairs:
        children[a].add(b)
    reached, pending = ({root}, [root]) if root in members and acyclic else (set(), [])
    while pending:
        extra = children[pending.pop()] - reached
        reached.update(extra)
        pending.extend(extra)
    anchors = {root} | {key for pair in pairs for key in pair}
    if anchors - reached:
        issue("disconnected_spine")
    covered = set()
    attachments = []
    for key in members & support:
        record = records[key]
        anchor = _text(record.get("stage_anchor_id"))
        if key in reached:
            if anchor != key:
                issue("invalid_stage_attachment")
            else:
                covered.add(key)
        elif (anchor in reached and anchor in support and anchor != key
                and _attributed(record.get("attachment_evidence_ids"), owners, {key, anchor})):
            covered.add(key)
            attachments.append([key, anchor])
        else:
            issue("invalid_stage_attachment")
    if not claim_complete:
        covered.clear()
    if members - covered:
        issue("unexplained_members")
    return {"group_id": group_id, "status": "evidence_linked" if members and not issues else "incomplete",
            "spine_depth": depth, "knowledge_depth": depth,
            "stage_anchor_ids": sorted(reached), "stage_attachments": attachments,
            "transition_pairs": [list(pair) for pair in sorted(pairs)],
            "covered_member_ids": sorted(covered), "unexplained_member_ids": sorted(members - covered),
            "issues": issues, "warnings": warnings}


def stage_connections(snapshot, reviewed_only=False):
    """Undirected membership links for coverage only; never evolution or discovery edges."""
    groups = {g["id"]: g for g in snapshot.get("groups", [])
              if g.get("explanation_model") == "knowledge_transitions_v1"}
    result = []
    if not groups:
        return result
    edges = snapshot.get("edges", [])
    if reviewed_only:
        edges = [edge for edge in edges if edge.get("semantic_review", {}).get("status") == "supported"]
    diagnostics = evaluate_groups(list(groups.values()), snapshot.get("nodes", []),
                                  edges, snapshot.get("comparisons", []))
    for item in diagnostics:
        group = groups[item["group_id"]]
        review = group.get("semantic_review", {}).get("status")
        if (review is not None and review != "supported") or (reviewed_only and review != "supported"):
            continue
        if item["status"] == "evidence_linked":
            result.extend(tuple(pair) for pair in item.get("stage_attachments", []))
    return result


def knowledge_metrics(snapshot):
    """Count independently reviewed before/after transitions, not raw paper paths."""
    groups = [g for g in snapshot.get("groups", []) if g.get("explanation_model") == "knowledge_transitions_v1"]
    if not groups:
        return {}
    reviewed = [g for g in groups if g.get("semantic_review", {}).get("status") == "supported"]
    edges = [e for e in snapshot.get("edges", []) if e.get("semantic_review", {}).get("status") == "supported"]
    diagnostics = evaluate_groups(reviewed, snapshot.get("nodes", []), edges, snapshot.get("comparisons", []))
    pairs = set()
    attachments = set()
    anchors = set()
    for item in diagnostics:
        if item["status"] != "evidence_linked":
            continue
        pairs.update(tuple(pair) for pair in item.get("transition_pairs", []))
        attachments.update(tuple(pair) for pair in item.get("stage_attachments", []))
        anchors.update(item.get("stage_anchor_ids", []))
    _, acyclic, depth = _spine_shape(pairs)
    return {"knowledge_depth": depth if acyclic else 0, "knowledge_transitions": len(pairs) if acyclic else 0,
            "stage_count": len(anchors), "attached_papers": len({a for a, b in attachments})}
