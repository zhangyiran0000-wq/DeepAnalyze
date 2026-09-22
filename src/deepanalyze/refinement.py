"""Deterministic refinement decisions and bounded, nonmutating graph patches.

The score measures retained explanatory structure, not scientific truth. Legacy
relations without a semantic review can support structural coverage, but never
reviewed depth. Explicitly insufficient or contradicted relations support neither.
"""

from __future__ import annotations

import copy
from collections import deque

from .graph import EDGE_KINDS, validate_edges
from .synthesis_quality import evaluate_groups, stage_connections, knowledge_metrics


_PROGRESSION = {"addresses", "builds_on"}
_CONNECTIONS = _PROGRESSION | {"challenges"}
_HARD_GROUP_ISSUES = {
    "empty_group", "incomplete_explanatory_claim", "missing_member_support",
    "invalid_member_support", "invalid_member_evidence", "invalid_spine_transition",
    "disconnected_spine", "cyclic_spine", "missing_spine", "semantic_claim_unverified",
    "missing_core_concept", "multiple_core_targets", "missing_label_nouns",
    "label_noun_limit_exceeded", "invalid_label_nouns", "duplicate_label_nouns",
    "duplicate_member_support", "missing_research_role", "missing_research_assessment", "invalid_stage_root",
    "missing_knowledge_transition", "redundant_knowledge_transition", "incremental_work_on_spine", "invalid_stage_attachment",
}


def _records(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _review_status(item):
    review = item.get("semantic_review")
    return review.get("status") if isinstance(review, dict) else None


def _eligible(item, reviewed_only=False):
    status = _review_status(item)
    if reviewed_only:
        return status == "supported"
    # Missing reviews are a compatibility allowance, not independent validation.
    return "semantic_review" not in item or status == "supported"


def _component(seed, nodes, edges, comparisons, stage_pairs=()):
    adjacency = {key: set() for key in nodes}
    pairs = [(e.get("source"), e.get("target")) for e in edges
             if e.get("status") == "supported" and e.get("kind") in _CONNECTIONS]
    pairs += [(c.get("source"), c.get("target")) for c in comparisons]
    pairs += list(stage_pairs)
    for source, target in pairs:
        if source in adjacency and target in adjacency:
            adjacency[source].add(target)
            adjacency[target].add(source)
    reached, pending = ({seed}, [seed]) if seed in nodes else (set(), [])
    while pending:
        neighbors = adjacency[pending.pop()] - reached
        reached.update(neighbors)
        pending.extend(neighbors)
    return reached


def _shape(nodes, edges):
    """Depth and forks of a DAG; redundant transitive links add no branches."""
    children = {key: set() for key in nodes}
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if (source in children and target in children and edge.get("status") == "supported"
                and edge.get("kind") in _PROGRESSION):
            children[source].add(target)
    indegree = dict.fromkeys(nodes, 0)
    for targets in children.values():
        for target in targets:
            indegree[target] += 1
    queue = deque(sorted(key for key, value in indegree.items() if value == 0))
    lengths = dict.fromkeys(nodes, 0)
    order = []
    while queue:
        source = queue.popleft()
        order.append(source)
        for target in sorted(children[source]):
            lengths[target] = max(lengths[target], lengths[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(order) != len(nodes):
        return 0, 0
    descendants = {key: set() for key in nodes}
    forks = 0
    for source in reversed(order):
        targets = children[source]
        direct = {target for target in targets
                  if not any(target in descendants[other] for other in targets - {target})}
        forks += max(0, len(direct) - 1)
        for target in targets:
            descendants[source].add(target)
            descendants[source].update(descendants[target])
    return max(lengths.values(), default=0), forks


def _assessment(snapshot, required_ids, knowledge_objective=False):
    snapshot = snapshot or {}
    nodes = {item["id"]: item for item in _records(snapshot.get("nodes")) if item.get("id")}
    groups = [group for group in _records(snapshot.get("groups")) if group.get("id") != "group_unresolved"]
    required = set(required_ids)
    owners, ambiguous = {}, set()
    for key, node in nodes.items():
        for evidence in _records(node.get("evidence")):
            ref = evidence.get("id")
            if not ref or evidence.get("verified") is not True:
                continue
            if ref in owners and owners[ref] != key:
                ambiguous.add(ref)
            else:
                owners[ref] = key
    for ref in ambiguous:
        owners.pop(ref, None)
    raw_edges = _records(snapshot.get("edges"))
    normalized, _, _ = validate_edges(list(nodes.values()), raw_edges)
    originals = {}
    for edge in raw_edges:
        kind = edge.get("kind", "related")
        kind = kind if kind in EDGE_KINDS else "related"
        originals.setdefault((edge.get("source"), edge.get("target"), kind), edge)
    edges, reviewed_edges = [], []
    invalid_edges = 0
    for edge in normalized:
        original = originals[(edge["source"], edge["target"], edge["kind"])]
        if original.get("status") == "supported" and edge.get("status") != "supported":
            invalid_edges += 1
        if "semantic_review" in original:
            edge["semantic_review"] = copy.deepcopy(original["semantic_review"])
        if _eligible(original):
            edges.append(edge)
        if _eligible(original, reviewed_only=True):
            reviewed_edges.append(edge)
    comparisons, reviewed_comparisons = [], []
    for item in _records(snapshot.get("comparisons")):
        source, target = item.get("source"), item.get("target")
        refs = item.get("evidence_ids")
        if not (source in nodes and target in nodes and source != target
                and item.get("grounded") is True and item.get("relation") == "alternative"
                and item.get("shared_problem") and isinstance(refs, list) and refs
                and all(ref in owners for ref in refs)
                and {owners[ref] for ref in refs} == {source, target}):
            continue
        if _eligible(item):
            comparisons.append(item)
        if _eligible(item, reviewed_only=True):
            reviewed_comparisons.append(item)
    grounded_nodes = {key for key, node in nodes.items()
                      if all(node.get(field) for field in ("problem", "mechanism", "solves"))
                      and any(e.get("verified") is True for e in _records(node.get("evidence")))}

    def coverage(links, parallels, reviewed_only=False):
        diagnostics = evaluate_groups(groups, list(nodes.values()), links, parallels)
        group_map = {group.get("id"): group for group in groups}
        for diagnostic in diagnostics:
            if not _eligible(group_map[diagnostic["group_id"]], reviewed_only):
                diagnostic["covered_member_ids"] = []
                diagnostic["issues"].append("semantic_claim_unverified")
                diagnostic["status"] = "incomplete"
        supported = {key for item in diagnostics for key in item["covered_member_ids"]}
        stage_view = {**snapshot, "edges": links, "comparisons": parallels}
        stage_pairs = stage_connections(stage_view, reviewed_only)
        connected = _component(snapshot.get("seed_id"), nodes, links, parallels, stage_pairs)
        return supported & grounded_nodes & connected, diagnostics, connected

    explained, diagnostics, connected = coverage(edges, comparisons)
    reviewed, _, reviewed_component = coverage(reviewed_edges, reviewed_comparisons, reviewed_only=True)
    hard = len(required - nodes.keys()) + len(nodes.keys() - grounded_nodes) + invalid_edges + len(required - connected)
    hard += sum(len(set(item["issues"]) & _HARD_GROUP_ISSUES) for item in diagnostics)
    memberships = [{key for key, node in nodes.items() if group.get("id") in node.get("group_ids", [])}
                   for group in groups]
    active = [members for members in memberships if members]
    depth, forks = _shape(reviewed_component & reviewed, reviewed_edges)
    if knowledge_objective or any(g.get("explanation_model") == "knowledge_transitions_v1" for g in groups):
        assessed = {**snapshot, "edges": reviewed_edges,
                    "nodes": [node for key, node in nodes.items() if key in reviewed_component & reviewed]}
        depth = knowledge_metrics(assessed).get("knowledge_depth", 0)
        valid_groups = [g for g in groups if g.get("semantic_review", {}).get("status") == "supported"]
        valid_stages = evaluate_groups(valid_groups, assessed["nodes"], reviewed_edges, reviewed_comparisons)
        # Virtual edges here describe already-validated stages for fork counting only.
        steps = [{"source": a, "target": b, "kind": "addresses", "status": "supported"}
                 for d in valid_stages if d["status"] == "evidence_linked" for a, b in d.get("transition_pairs", [])]
        _, forks = _shape(reviewed_component & reviewed, steps)
    branches = max(0, len(active) - 1) + forks
    singletons = sum(len(members) == 1 for members in active)
    score = (len(explained & required), -hard, depth, -branches, -singletons)
    return {"score": score, "nodes": set(nodes), "explained": explained,
            "reviewed": reviewed, "reviewed_depth": depth}


def candidate_score(snapshot, required_ids):
    """Higher is better: coverage, hard validity, reviewed knowledge depth, fewer branches.

    The final item prefers fewer singleton groups. Edge counts and self-reported
    metrics are never rewards. Existing completion-blocking schema defects are
    included before depth; singleton groups remain a soft final preference.
    """
    return _assessment(snapshot, required_ids)["score"]


def choose_candidate(previous, candidate, required_ids):
    """Return (selected snapshot, decision); ties keep the previous object.

    Coverage preservation is set-based: gaining two papers cannot compensate for
    losing a previously explained one. All old nodes and reviewed coverage must
    also survive. Neither snapshot is mutated.
    """
    required = set(required_ids)
    knowledge_objective = any(g.get("explanation_model") == "knowledge_transitions_v1"
                              for value in (previous or {}, candidate or {}) for g in value.get("groups", []))
    before = _assessment(previous, required, knowledge_objective)
    after = _assessment(candidate, required, knowledge_objective)
    if previous is None:
        accepted, reason = True, "Retain the first candidate as the initial working explanation."
    elif before["nodes"] - after["nodes"]:
        accepted, reason = False, "Candidate removed previously retained sources."
    elif before["explained"] - after["explained"]:
        accepted, reason = False, "Candidate lost previously explained source coverage."
    elif before["reviewed"] - after["reviewed"]:
        accepted, reason = False, "Candidate lost independently reviewed source coverage."
    elif after["score"] > before["score"]:
        accepted, reason = True, "Candidate improved the ordered refinement objective without coverage loss."
    elif after["score"] == before["score"]:
        accepted, reason = False, "Candidate tied the retained explanation; keep the earlier version."
    else:
        accepted, reason = False, "Candidate regressed on the ordered refinement objective."
    return (candidate if accepted else previous), {
        "accepted": accepted, "reason": reason,
        "before": list(before["score"]), "after": list(after["score"]),
    }


def local_patch_proposal(proposal, base, focus_ids, allow_regroup=False):
    """Restrict model changes before passing the proposal to build_snapshot.

    Local calls may change focus nodes and relations touching a focus node whose
    other endpoint is retained or in focus. Existing memberships and group claims
    are frozen. New unassigned focus nodes await an explicit regroup phase.
    ``allow_regroup=True`` permits a full group replacement, including memberships;
    node and relation edits remain restricted to focus in either mode.
    """
    focus = set(focus_ids)
    base = base or {}
    nodes = {item["id"]: item for item in _records(base.get("nodes")) if item.get("id")}
    allowed = set(nodes) | focus
    result = copy.deepcopy(proposal)
    result["update_mode"] = "incremental"
    changes = []
    for incoming in _records(proposal.get("nodes")):
        key = incoming.get("id")
        if key not in focus:
            continue
        node = {**copy.deepcopy(nodes.get(key, {})), **copy.deepcopy(incoming)}
        if not allow_regroup:
            node["group_ids"] = copy.deepcopy(nodes.get(key, {}).get("group_ids", []))
        changes.append(node)
    result["nodes"] = changes
    for kind in ("edges", "comparisons"):
        result[kind] = [copy.deepcopy(item) for item in _records(proposal.get(kind))
                        if item.get("source") in allowed and item.get("target") in allowed
                        and {item.get("source"), item.get("target")} & focus]
    if not allow_regroup:
        result["groups"] = copy.deepcopy(_records(base.get("groups")))
        for group in result["groups"]:
            group["member_ids"] = sorted(key for key, node in nodes.items()
                                         if group.get("id") in node.get("group_ids", []))
            group.pop("merge_from", None)
    else:
        result["groups"] = copy.deepcopy(_records(proposal.get("groups")))
    gaps = [copy.deepcopy(item) for item in _records(base.get("gaps"))
            if not set(item.get("paper_ids", [])) & focus]
    gaps += [copy.deepcopy(item) for item in _records(proposal.get("gaps"))
             if set(item.get("paper_ids", [])) & focus]
    result["gaps"] = gaps
    result["dispositions"] = [copy.deepcopy(item) for item in _records(proposal.get("dispositions"))
                              if item.get("paper_id") in focus]
    return result
