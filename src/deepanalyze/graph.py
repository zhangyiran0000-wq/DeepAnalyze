"""Normalize evidence-linked proposals before computing conservative graph depth.

Quote grounding checks attribution only. Neither this validator nor the depth
metric establishes that a scientific explanation is true or historically causal.
"""

from __future__ import annotations

import copy
import hashlib
import re
import uuid
from datetime import date
from urllib.parse import urlsplit

from .store import utc_now
from .synthesis_quality import evaluate_groups, knowledge_metrics

PALETTE = ["#64c8b5", "#a49bea", "#dfad68", "#78addd", "#d887a7", "#a5be73"]
EDGE_KINDS = {"addresses", "builds_on", "challenges", "related"}


def stable_id(prefix: str, *parts) -> str:
    digest = hashlib.sha256("\x1f".join(str(part) for part in parts).encode()).hexdigest()[:16]
    return f"{prefix}_{digest}"


def normalized(text) -> str:
    return " ".join(str(text or "").split())


def clean_text(value, limit=3000) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def text_list(value, limit=12) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [clean_text(item) for item in value[:limit] if clean_text(item)]


def safe_url(value) -> str:
    if not isinstance(value, str):
        return ""
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
            return ""
        return value[:2000]
    except ValueError:
        return ""


def _year(value):
    try:
        year = int(value)
        return year if 1000 <= year <= 3000 else None
    except (ValueError, TypeError):
        return None


def _date_key(node):
    raw = node.get("date") or ""
    try:
        return date.fromisoformat(raw[:10]).toordinal()
    except (ValueError, TypeError):
        year = _year(node.get("year"))
        return date(year, 1, 1).toordinal() if year else None


def _date_bounds(node):
    """A year-only date is an interval; never invent January publication order."""
    raw = node.get("date") or ""
    try:
        value = date.fromisoformat(raw[:10]).toordinal()
        return value, value
    except (ValueError, TypeError):
        year = _year(node.get("year"))
        return (date(year, 1, 1).toordinal(), date(year, 12, 31).toordinal()) if year else (None, None)


def _reaches(adjacency: dict, start, goal) -> bool:
    stack, seen = [start], set()
    while stack:
        item = stack.pop()
        if item == goal:
            return True
        if item not in seen:
            seen.add(item)
            stack.extend(adjacency.get(item, []))
    return False


def validate_edges(nodes: list[dict], edges: list[dict]) -> tuple[list[dict], list[dict], dict]:
    """Reject impossible links and retain ungrounded proposals as hypotheses."""
    node_map = {node["id"]: node for node in nodes}
    evidence_owner = {
        item["id"]: node["id"] for node in nodes for item in node.get("evidence", [])
        if item.get("verified")
    }
    adjacency = {node_id: [] for node_id in node_map}
    result, gaps, seen = [], [], set()
    for incoming in edges:
        if not isinstance(incoming, dict):
            continue
        source, target = incoming.get("source"), incoming.get("target")
        if source not in node_map or target not in node_map:
            continue
        kind = incoming.get("kind", "related")
        if kind not in EDGE_KINDS:
            kind = "related"
        identity = (source, target, kind)
        if identity in seen:
            continue
        seen.add(identity)
        edge = {
            "id": stable_id("edge", *identity), "source": source, "target": target, "kind": kind,
            "problem": clean_text(incoming.get("problem")),
            "mechanism": clean_text(incoming.get("mechanism")),
            "consequence": clean_text(incoming.get("consequence")),
            "evidence_ids": list(dict.fromkeys(
                item for item in incoming.get("evidence_ids", [])
                if isinstance(item, str) and evidence_owner.get(item) in {source, target}
            )) if isinstance(incoming.get("evidence_ids", []), list) else [],
            "status": incoming.get("status") if incoming.get("status") in {"supported", "hypothesis", "rejected"} else "hypothesis",
            "rationale": clean_text(incoming.get("rationale")),
            "historical_influence": incoming.get("historical_influence") if incoming.get("historical_influence") in {"documented", "unknown", "not_claimed"} else "unknown",
            "conditions": text_list(incoming.get("conditions")),
        }
        issue = ""
        source_time, _ = _date_bounds(node_map[source])
        _, target_time = _date_bounds(node_map[target])
        if source_time is not None and target_time is not None and (
            len(str(node_map[source].get("date") or "")) < 10 or len(str(node_map[target].get("date") or "")) < 10
        ):
            edge["conditions"].append("At least one source has year-only publication precision; within-year historical order is not established.")
        if source == target:
            issue, edge["status"] = "Self-links do not establish a technical transition.", "rejected"
        elif source_time is not None and target_time is not None and source_time > target_time:
            issue, edge["status"] = "The proposed direction runs backward in publication time.", "rejected"
        elif (source_time is None or target_time is None) and edge["status"] != "rejected":
            issue, edge["status"] = "Publication dates must be resolved before this link can count toward depth.", "hypothesis"
        elif edge["status"] == "supported":
            owners = {evidence_owner[item] for item in edge["evidence_ids"]}
            if owners != {source, target} or not edge["problem"] or not edge["mechanism"]:
                issue, edge["status"] = "Both endpoint sources and a specific problem/mechanism are required; the link remains a hypothesis.", "hypothesis"
            elif kind in {"addresses", "builds_on"} and _reaches(adjacency, target, source):
                issue, edge["status"] = "This link would introduce a cycle and cannot count toward depth.", "rejected"
        if edge["status"] == "supported" and kind in {"addresses", "builds_on"}:
            adjacency[source].append(target)
        edge["conditions"] = list(dict.fromkeys(edge["conditions"]))
        if issue and issue not in edge["rationale"]:
            edge["rationale"] = (edge["rationale"] + " " + issue).strip()
        if edge["status"] != "supported":
            gaps.append({"id": stable_id("gap", edge["id"]),
                         "description": issue or edge["rationale"] or "This proposed relationship remains unverified.",
                         "paper_ids": [source, target]})
        result.append(edge)
    indegree = dict.fromkeys(node_map, 0)
    for neighbors in adjacency.values():
        for target in neighbors:
            indegree[target] += 1
    queue = sorted(key for key, value in indegree.items() if not value)
    lengths = dict.fromkeys(node_map, 0)
    while queue:
        source = queue.pop(0)
        for target in adjacency[source]:
            lengths[target] = max(lengths[target], lengths[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    metrics = {
        "depth": max(lengths.values(), default=0), "node_count": len(nodes), "edge_count": len(result),
        "supported_edges": sum(edge["status"] == "supported" for edge in result),
    }
    return result, gaps, metrics


def _verified_evidence(proposed, paper, previous) -> list[dict]:
    existing = {item["id"]: copy.deepcopy(item) for item in previous if item.get("verified")}
    passages = paper.get("passages", [])
    if not isinstance(proposed, list):
        return list(existing.values())
    for item in proposed[:30]:
        if not isinstance(item, dict):
            continue
        quote = clean_text(item.get("quote"), 2000)
        if len(normalized(quote)) < 12:
            continue
        for passage in passages:
            if normalized(quote) in normalized(passage.get("text")):
                evidence_id = stable_id("ev", paper["id"], normalized(quote))
                existing[evidence_id] = {
                    "id": evidence_id, "quote": quote,
                    "source_url": safe_url(passage.get("url") or paper.get("url")),
                    "location": clean_text(passage.get("location") or passage.get("id") or "Source passage", 200),
                    "kind": "abstract" if "abstract" in str(passage.get("location", "")).lower() else "passage",
                    "verified": True,
                }
                break
    return list(existing.values())


def _affiliations(paper) -> list[dict]:
    """Only render institutions with an attribution snippet supplied by the source."""
    result = []
    passages = " ".join(normalized(p.get("text")) for p in paper.get("passages", []))
    for item in paper.get("affiliations", []):
        if not isinstance(item, dict):
            continue
        name, quote = clean_text(item.get("name"), 200), normalized(item.get("quote"))
        if name and quote and quote in passages and normalized(name).lower() in quote.lower():
            result.append({"name": name, "url": safe_url(item.get("url")), "quote": quote,
                           "source_url": safe_url(item.get("source_url") or paper.get("url"))})
    return result


def build_snapshot(proposal: dict, papers: dict[str, dict], previous: dict | None,
                   seed_id: str, scope: str, iteration: int, demo=False) -> dict:
    """Bind model claims to retrieved identities and evidence; compute graph metrics."""
    if not isinstance(proposal, dict):
        raise ValueError("The synthesis response must be an object.")
    previous = previous or {}
    old_nodes = {node["id"]: node for node in previous.get("nodes", [])}
    old_groups = {group["id"]: group for group in previous.get("groups", [])}
    # Groups are a replaceable partition, not an append-only history.
    groups = {}
    merges, memberships = {}, {}
    notes = text_list(proposal.get("review_notes"), 30)
    for item in proposal.get("groups", [])[:30]:
        if not isinstance(item, dict) or not clean_text(item.get("label")):
            continue
        label = clean_text(item["label"], 120)
        prior = old_groups.get(item.get("id")) or next((g for g in old_groups.values() if g["label"].casefold() == label.casefold()), None)
        group_id = prior["id"] if prior else clean_text(item.get("id"), 100) or stable_id("group", label.casefold())
        groups[group_id] = {"id": group_id, "label": label,
                            "description": clean_text(item.get("description")),
                            "color": prior["color"] if prior else PALETTE[len(groups) % len(PALETTE)]}
        for field in ("common_problem", "progression", "open_problem", "separation_reason"):
            if item.get(field):
                groups[group_id][field] = clean_text(item[field])
        groups[group_id]["core_concept"] = clean_text(item.get("core_concept"), 200)
        groups[group_id]["label_nouns"] = text_list(item.get("label_nouns"), 30)
        claim = item.get("explanatory_claim") or {}
        groups[group_id]["explanatory_claim"] = {field: clean_text(claim.get(field)) for field in ("constraint", "mechanism", "consequence")} if isinstance(claim, dict) else {}
        # The contract fields are opt-in for legacy snapshots: do not invent
        # a transition model when an older proposal did not provide one.
        contract_keys = ("explanation_model", "root_id")
        if any(key in item or (prior and key in prior) for key in contract_keys):
            model = item.get("explanation_model", prior.get("explanation_model") if prior else None)
            if model == "knowledge_transitions_v1":
                groups[group_id]["explanation_model"] = model
            root_id = clean_text(item.get("root_id", prior.get("root_id") if prior else None), 200)
            if root_id:
                groups[group_id]["root_id"] = root_id
        groups[group_id]["spine"] = []
        for link in (item.get("spine") or [])[:250]:
            if not isinstance(link, dict):
                continue
            record = {field: clean_text(link.get(field)) for field in ("source", "target", "claim_connection")}
            if any(field in link for field in ("before", "after", "transition_type")):
                record["before"] = clean_text(link.get("before"), 900)
                record["after"] = clean_text(link.get("after"), 900)
                transition = link.get("transition_type")
                record["transition_type"] = transition if transition in {"advance", "revision", "reframing"} else ""
            groups[group_id]["spine"].append(record)
        groups[group_id]["member_support"] = []
        for record in (item.get("member_support") or [])[:500]:
            if not isinstance(record, dict):
                continue
            support = {"paper_id": clean_text(record.get("paper_id")),
                       "claim_connection": clean_text(record.get("claim_connection")),
                       "evidence_ids": text_list(record.get("evidence_ids"), 30)}
            if any(field in record for field in ("role", "stage_anchor_id", "knowledge_change", "removal_effect", "attachment_evidence_ids")):
                role = record.get("role")
                support.update({"role": role if role in {"advance", "revision", "proposal", "incremental", "replication", "tooling"} else "",
                    "stage_anchor_id": clean_text(record.get("stage_anchor_id"), 200),
                    "knowledge_change": clean_text(record.get("knowledge_change"), 900),
                    "removal_effect": clean_text(record.get("removal_effect"), 900),
                    "attachment_evidence_ids": text_list(record.get("attachment_evidence_ids"), 30)})
            groups[group_id]["member_support"].append(support)
        memberships[group_id] = text_list(item.get("member_ids"), 500)
        for merged_id in text_list(item.get("merge_from"), 100):
            if merged_id in old_groups and merged_id != group_id:
                merges[merged_id] = group_id

    unresolved_id = "group_unresolved"
    if not groups:
        groups[unresolved_id] = {"id": unresolved_id, "label": "Unresolved structure",
                                 "description": "No evidence-backed organizing logic has been established yet.", "color": PALETTE[0]}
    nodes = copy.deepcopy(old_nodes)
    evidence_aliases = {}

    def resolve_evidence_refs(refs, allowed_owners):
        result = []
        for ref in text_list(refs, 30):
            matches = {canonical for owner, canonical in evidence_aliases.get(ref, set()) if owner in allowed_owners}
            if len(matches) == 1:
                result.append(next(iter(matches)))
            elif not matches:
                result.append(ref)
            # An ambiguous shared alias cannot prove either endpoint. Members
            # can disambiguate by their own paper_id, unlike a two-paper edge.
        return result
    for item in proposal.get("nodes", [])[:250]:
        if not isinstance(item, dict):
            continue
        paper_id = item.get("id")
        if paper_id not in papers:
            notes.append("A proposed node was excluded because its identity was not in the retrieved source set.")
            continue
        paper, old = papers[paper_id], old_nodes.get(paper_id, {})
        evidence = _verified_evidence(item.get("evidence", []), paper, old.get("evidence", []))
        for raw in item.get("evidence", []) if isinstance(item.get("evidence"), list) else []:
            if isinstance(raw, dict):
                verified = next((ev for ev in evidence if normalized(ev["quote"]) == normalized(raw.get("quote"))), None)
                if verified and isinstance(raw.get("id"), str):
                    evidence_aliases.setdefault(raw["id"], set()).add((paper_id, verified["id"]))
        node_groups = [group_id for group_id in text_list(item.get("group_ids")) if group_id in groups]
        if not node_groups:
            if unresolved_id not in groups:
                groups[unresolved_id] = {"id": unresolved_id, "label": "Unresolved structure", "description": "This work is not yet assigned to a supported line.", "color": "#8994a5"}
            node_groups = [merges.get(g, g) for g in old.get("group_ids", []) if merges.get(g, g) in groups] or [unresolved_id]
        nodes[paper_id] = {
            "id": paper_id, "title": clean_text(paper.get("title"), 500),
            "short_name": clean_text(item.get("short_name") or paper.get("short_name") or paper.get("title"), 100),
            "year": _year(paper.get("year")), "date": clean_text(paper.get("date"), 20),
            "url": safe_url(paper.get("url")), "authors": copy.deepcopy(paper.get("authors", [])),
            "author_ids": text_list(paper.get("author_ids", old.get("author_ids", [])), 1000),
            "affiliations": _affiliations(paper), "group_ids": node_groups,
            "problem": clean_text(item.get("problem")), "mechanism": clean_text(item.get("mechanism")),
            "solves": clean_text(item.get("solves")), "results": clean_text(item.get("results")),
            "limitations": text_list(item.get("limitations")), "assumptions": text_list(item.get("assumptions")),
            "uncertainties": text_list(item.get("uncertainties")), "evidence": evidence,
            "source_status": clean_text(paper.get("source_status") or "metadata_only", 120),
            **{key: clean_text(paper.get(key) or old.get(key), 2000) for key in (
                "context_role", "context_reason", "context_for", "context_problem", "context_evidence_quote", "forward_citation_of")
               if paper.get(key) or old.get(key)},
            "citation_links": copy.deepcopy(paper.get("citation_links", old.get("citation_links", []))),
            "external_ids": copy.deepcopy(paper.get("external_ids", old.get("external_ids", {}))),
            "added_iteration": old.get("added_iteration", iteration),
        }
        raw_assessment = item.get("research_assessment", old.get("research_assessment"))
        if isinstance(raw_assessment, dict):
            outcome = raw_assessment.get("outcome")
            valid_outcomes = {"demonstrated", "partial", "not_tested", "contradicted", "unknown"}
            assessment_refs = resolve_evidence_refs(raw_assessment.get("evidence_ids"), {paper_id})
            if outcome not in valid_outcomes:
                outcome = "unknown"
            nodes[paper_id]["research_assessment"] = {
                "outcome": outcome,
                "claimed_problem": clean_text(raw_assessment.get("claimed_problem"), 1200),
                "demonstrated_result": clean_text(raw_assessment.get("demonstrated_result"), 1200),
                "conditions": clean_text(raw_assessment.get("conditions"), 1200),
                "unresolved": clean_text(raw_assessment.get("unresolved"), 1200),
                "evidence_ids": list(dict.fromkeys(assessment_refs)),
            }
        observations = item.get("research_observations", old.get("research_observations", []))
        nodes[paper_id]["research_observations"] = []
        for observation in observations[:10] if isinstance(observations, list) else []:
            if not isinstance(observation, dict) or observation.get("kind") not in {"claimed_problem", "demonstrated_gain", "evaluation_protocol", "limitation", "positioning"}:
                continue
            refs = resolve_evidence_refs(observation.get("evidence_ids", []), {paper_id})
            refs = [ref for ref in refs if any(ev["id"] == ref and ev.get("verified") for ev in evidence)]
            basis = observation.get("basis", "unknown")
            if basis not in {"author_claim", "reported_experiment", "model_inference", "unknown"} or not refs:
                basis = "unknown"
            nodes[paper_id]["research_observations"].append({"kind": observation["kind"],
                "statement": clean_text(observation.get("statement"), 3000), "basis": basis, "evidence_ids": refs})
        if not evidence:
            nodes[paper_id]["uncertainties"].append("No proposed quotation could be verified against supplied source passages; the analysis remains provisional.")
    if seed_id not in nodes and seed_id in papers:
        seed = papers[seed_id]
        nodes[seed_id] = {
            "id": seed_id, "title": seed.get("title", "Seed paper"), "short_name": seed.get("short_name") or "Seed",
            "year": _year(seed.get("year")), "date": seed.get("date", ""), "url": safe_url(seed.get("url")),
            "authors": seed.get("authors", []), "author_ids": text_list(seed.get("author_ids"), 1000), "affiliations": _affiliations(seed), "group_ids": [next(iter(groups))],
            "problem": "", "mechanism": "", "solves": "", "results": "", "limitations": [], "assumptions": [],
            "uncertainties": ["The seed has not yet received a source-grounded analysis."], "evidence": [],
            "source_status": seed.get("source_status", "metadata_only"), "added_iteration": iteration,
            "external_ids": copy.deepcopy(seed.get("external_ids", {})),
        }
    # Membership lists can regroup untouched historical nodes without forcing
    # a fresh per-paper summary. Explicit merge operators remap old memberships.
    assigned = {}
    for group_id, paper_ids in memberships.items():
        for paper_id in paper_ids:
            if paper_id in nodes:
                assigned.setdefault(paper_id, []).append(group_id)
    for paper_id, node in nodes.items():
        selected = assigned.get(paper_id) or [merges.get(g, g) for g in node.get("group_ids", []) if merges.get(g, g) in groups]
        if not selected:
            groups.setdefault(unresolved_id, {"id": unresolved_id, "label": "Pending synthesis",
                              "description": "Insufficient evidence to assign a shared problem line.", "color": "#8994a5"})
            selected = [unresolved_id]
        node["group_ids"] = list(dict.fromkeys(selected))
    used = {g for node in nodes.values() for g in node["group_ids"]}
    groups = {g: value for g, value in groups.items() if g in used}
    counts = {g: sum(g in n["group_ids"] for n in nodes.values()) for g in groups}
    comparisons = []
    # A model can cite the exact ID of a short retrieved passage instead of
    # minting another quote alias. Resolve it against that endpoint's source,
    # retaining the whole passage as visible evidence; never guess or truncate.
    referenced = {key: set(node.get("research_assessment", {}).get("evidence_ids", [])) for key, node in nodes.items()}
    for group in groups.values():
        for record in group.get("member_support", []):
            referenced.setdefault(record["paper_id"], set()).update(record.get("evidence_ids", []))
            for owner in (record["paper_id"], record.get("stage_anchor_id")):
                referenced.setdefault(owner, set()).update(record.get("attachment_evidence_ids", []))
    for record in proposal.get("edges", []) + proposal.get("comparisons", []):
        if isinstance(record, dict):
            for owner in (record.get("source"), record.get("target")):
                referenced.setdefault(owner, set()).update(text_list(record.get("evidence_ids"), 30))
    for owner, refs in referenced.items():
        if owner not in nodes or owner not in papers:
            continue
        for passage in papers[owner].get("passages", []):
            ref, quote = passage.get("id"), clean_text(passage.get("text"), 100000)
            if (ref not in refs or not 12 <= len(quote) <= 2000
                    or passage.get("kind") == "metadata_affiliation"
                    or "metadata" in passage.get("location", "").lower()
                    or any(key == owner for key, _ in evidence_aliases.get(ref, set()))):
                continue
            evidence = _verified_evidence([{"quote": quote}], papers[owner], nodes[owner].get("evidence", []))
            match = next((ev for ev in evidence if normalized(ev["quote"]) == normalized(quote)), None)
            if match:
                nodes[owner]["evidence"] = evidence
                evidence_aliases.setdefault(ref, set()).add((owner, match["id"]))
    evidence_owner = {ev["id"]: n["id"] for n in nodes.values() for ev in n.get("evidence", []) if ev.get("verified")}
    for key, node in nodes.items():
        assessment = node.get("research_assessment")
        if isinstance(assessment, dict):
            assessment["evidence_ids"] = [ref for ref in resolve_evidence_refs(assessment.get("evidence_ids", []), {key})
                                          if evidence_owner.get(ref) == key]
            if assessment.get("outcome") == "demonstrated" and not assessment["evidence_ids"]:
                assessment["outcome"] = "unknown"
    seen_pairs = set()
    # New decisions supersede previous pairs; unchanged evidence-linked comparisons
    # are reused rather than regenerated on every iteration.
    comparison_updates = proposal.get("comparisons", [])[:150]
    if proposal.get("update_mode") == "incremental":
        comparison_updates = comparison_updates + previous.get("comparisons", [])
    for raw in comparison_updates:
        if not isinstance(raw, dict):
            continue
        a, b = raw.get("source"), raw.get("target")
        if a not in nodes or b not in nodes or a == b or tuple(sorted((a, b))) in seen_pairs:
            continue
        seen_pairs.add(tuple(sorted((a, b))))
        item = {"id": stable_id("comparison", a, b), "source": a, "target": b}
        for field in ("shared_problem", "earlier_limitation", "later_change", "remaining_gap", "relation", "group_action", "rationale"):
            item[field] = clean_text(raw.get(field))
        refs = resolve_evidence_refs(raw.get("evidence_ids"), {a, b})
        item["evidence_ids"] = [ref for ref in refs if evidence_owner.get(ref) in {a, b}]
        item["grounded"] = {evidence_owner[ref] for ref in item["evidence_ids"]} == {a, b}
        if not item["grounded"]:
            item["relation"] = "insufficient_evidence"
            item["group_action"] = "uncertain"
        comparisons.append(item)
    independent = {g for g, value in groups.items() if value.get("separation_reason")}
    singleton_groups = [g for g, count in counts.items() if count == 1 and g != unresolved_id]
    fragmented = len(nodes) >= 3 and len(singleton_groups) >= len(nodes) * .75
    unmerged = [item for item in comparisons if item["group_action"] == "merge" and item["grounded"] and item["relation"] in {"progression", "alternative"} and
               not set(nodes[item["source"]]["group_ids"]) & set(nodes[item["target"]]["group_ids"])]
    split_progressions = [item for item in comparisons if item["grounded"] and item["relation"] == "progression" and
                          not set(nodes[item["source"]]["group_ids"]) & set(nodes[item["target"]]["group_ids"])]
    synthesis_quality = {
        "group_count": len(groups), "singleton_groups": len(singleton_groups),
        "comparison_count": len(comparisons), "unresolved_merges": len(unmerged),
        "split_progressions": len(split_progressions),
        "needs_consolidation": bool(unmerged or split_progressions or (fragmented and any(g not in independent for g in singleton_groups))),
        "status": "fragmented" if fragmented else "proposed",
    }
    if fragmented:
        notes.append("Most papers still occupy singleton groups. This is a fragmented classification, not an established research mainline; inspect separation reasons and cross-paper comparisons.")
    if unmerged:
        notes.append("Some grounded comparisons call for merging groups that remain separate. Further consolidation is required.")
    if split_progressions:
        notes.append("A proposed problem progression crosses separate lines. Recheck shared bottlenecks and memberships: missing historical citation alone does not justify splitting a technical progression.")
    edge_proposals = copy.deepcopy(proposal.get("edges", []))
    for edge in edge_proposals:
        if isinstance(edge, dict) and isinstance(edge.get("evidence_ids"), list):
            edge["evidence_ids"] = resolve_evidence_refs(edge["evidence_ids"], {edge.get("source"), edge.get("target")})
    if proposal.get("update_mode") == "incremental":
        # Incoming decisions come first, so validate_edges keeps an explicit
        # rejection or correction in preference to the stored decision.
        edge_proposals.extend(copy.deepcopy(previous.get("edges", [])))
    # Legacy full proposals still replace edges; incremental proposals must
    # explicitly reject a link to retract it. Previous snapshots stay immutable.
    edges, validation_gaps, metrics = validate_edges(list(nodes.values()), edge_proposals)
    for group in groups.values():
        anchors = set()
        if group.get("root_id"):
            anchors.add(group["root_id"])
        for spine in group.get("spine", []):
            anchors.update(value for value in (spine.get("source"), spine.get("target")) if value)
        for record in group.get("member_support", []):
            record["evidence_ids"] = resolve_evidence_refs(record["evidence_ids"], {record["paper_id"]})
            if "attachment_evidence_ids" in record:
                anchor = record.get("stage_anchor_id")
                if anchor not in anchors:
                    record["stage_anchor_id"] = ""
                    record["attachment_evidence_ids"] = []
                else:
                    owners = {record["paper_id"], anchor}
                    record["attachment_evidence_ids"] = [ref for ref in resolve_evidence_refs(record.get("attachment_evidence_ids"), owners)
                        if evidence_owner.get(ref) in owners]
    group_quality = evaluate_groups(list(groups.values()), list(nodes.values()), edges, comparisons)
    for quality in group_quality:
        groups[quality["group_id"]]["explanation_quality"] = quality
    synthesis_quality["group_diagnostics"] = group_quality
    synthesis_quality["incomplete_groups"] = sum(q["status"] == "incomplete" for q in group_quality)
    synthesis_quality["needs_consolidation"] |= bool(synthesis_quality["incomplete_groups"])
    synthesis_quality["status"] = "incomplete" if synthesis_quality["incomplete_groups"] else "evidence_linked"
    gaps = []
    for item in proposal.get("gaps", [])[:100]:
        if isinstance(item, dict) and clean_text(item.get("description")):
            description = clean_text(item["description"])
            gaps.append({"id": clean_text(item.get("id"), 100) or stable_id("gap", description),
                         "description": description,
                         "paper_ids": [value for value in text_list(item.get("paper_ids"), 100) if value in nodes]})
    gaps.extend(validation_gaps)
    notes.append("Verified quotations establish source attribution only. Supported links are evidence-linked model interpretations, not independently proven scientific or historical causality.")
    changes = []
    for key in ("nodes", "edges", "groups", "gaps"):
        before = {item["id"]: item for item in previous.get(key, [])}
        after_values = {"nodes": list(nodes.values()), "edges": edges, "groups": list(groups.values()), "gaps": gaps}[key]
        after = {item["id"]: item for item in after_values}
        for item_id in sorted(after.keys() - before.keys()):
            changes.append({"kind": "added", "target_id": item_id, "reason": f"Added {key[:-1]} in this iteration."})
        for item_id in sorted(before.keys() - after.keys()):
            changes.append({"kind": "removed", "target_id": item_id, "reason": f"The current synthesis did not retain this {key[:-1]}; the prior snapshot remains available."})
        for item_id in sorted(before.keys() & after.keys()):
            if before[item_id] != after[item_id]:
                reason = "Revised after reviewing this iteration's evidence."
                if key == "edges" and before[item_id].get("status") == "supported" and after[item_id].get("status") != "supported":
                    reason = "Retracted supported status: " + after[item_id].get("rationale", "Further support is required.")
                changes.append({"kind": "updated", "target_id": item_id, "reason": reason})
    snapshot = {"id": uuid.uuid4().hex, "iteration": iteration, "created_at": utc_now(),
            "seed_id": seed_id, "scope": scope, "groups": list(groups.values()),
            "nodes": sorted(nodes.values(), key=lambda node: (_date_key(node) or 0, node["id"])),
            "edges": edges, "comparisons": comparisons, "synthesis_quality": synthesis_quality,
            "gaps": gaps, "changes": changes, "metrics": metrics,
            "review_notes": list(dict.fromkeys(notes)), "demo": bool(demo)}
    metrics.update(knowledge_metrics(snapshot))
    return snapshot
