"""Entirely fictional fixtures for previewing the interface without model usage.

Every title, author, institution, observation, and quotation below is synthetic.
These are not research results, references, or claims about actual systems.
"""

from __future__ import annotations

from .graph import build_snapshot

DEMO_SCOPE = "Synthetic demonstration: follow fictional ledger designs as storage limits create correction and audit problems. No item represents a real publication."

_ITEMS = [
    ("ledger", "Full Ledger — synthetic example", "Full ledger", "2018-01-01", "storage",
     "Historical records must remain individually inspectable.", "Retain every record in order.",
     "Provides a baseline with direct access to each record.", "Stored records grow with the number of arrivals.",
     "The synthetic baseline stores every incoming record. Its stored record count grows with the number of arrivals."),
    ("window", "Window Ledger — synthetic example", "Window ledger", "2019-03-01", "storage",
     "The baseline stores an unbounded number of records.", "Retain only the four most recent records.",
     "Bounds retained record count by discarding older records.", "Discarded records cannot be read from this store.",
     "This fictional design keeps only the four most recent records. Earlier records are discarded and cannot be recovered from the window."),
    ("summary", "Summary Ledger — synthetic example", "Summary ledger", "2020-02-01", "storage",
     "A short window loses earlier contributions to aggregate totals.", "Accumulate category totals in a fixed collection of counters.",
     "Retains aggregate contributions without preserving individual records.", "Individual record identities are unavailable after aggregation.",
     "This synthetic design accumulates category totals in a fixed collection of counters. It retains contributions but removes individual record identities."),
    ("correction", "Correctable Ledger — synthetic example", "Correctable ledger", "2021-06-01", "correction",
     "An aggregate cannot directly replace a specific earlier contribution.", "Attach a bounded correction table to the category counters.",
     "Replaces earlier contributions while their keys remain in the correction table.", "Corrections for evicted keys remain unresolved.",
     "The fictional correction table allows a retained key's previous contribution to be replaced. The demonstration provides no recovery mechanism for evicted keys."),
    ("sketch", "Audit Sketch — synthetic example", "Audit sketch", "2021-06-01", "audit",
     "Aggregate totals can conceal mismatched updates.", "Store a compact signature alongside each aggregate.",
     "Flags selected inconsistencies in a synthetic check.", "A detected mismatch does not identify the original missing record.",
     "A synthetic signature flags mismatched updates in the example cases. Detection alone does not identify the original missing record or repair the ledger."),
    ("hybrid", "Checked Corrections — synthetic example", "Checked corrections", "2023-04-01", "correction",
     "Corrections and mismatch detection are handled separately.", "Combine the bounded correction table with the audit signature.",
     "Uses a mismatch signal to inspect retained correction entries.", "The design still cannot reconstruct an evicted record.",
     "This fictional design combines the correction table with the audit signature. A mismatch triggers inspection of retained entries, but evicted records remain unavailable."),
    ("audit", "Hidden Work Audit — synthetic example", "Hidden-work audit", "2024-09-01", "audit",
     "The combined design's extra checking work has not been accounted for.", "Count the signature checks and correction-table probes separately.",
     "Challenges an earlier assumption that bounded storage implies constant total cost.", "This synthetic audit does not establish real-world performance.",
     "The example audit counts signature checks and correction-table probes separately. Bounded stored state does not by itself establish bounded total work."),
]


def demo_snapshot(iteration: int, previous=None) -> dict:
    stage = min(3, max(1, iteration))
    count = {1: 3, 2: 5, 3: 7}[stage]
    papers, nodes = {}, []
    for index, (paper_id, title, short, published, group, problem, mechanism, solves, limitation, quote) in enumerate(_ITEMS[:count]):
        organization = "Synthetic Example Lab" if index % 2 else "Fictional Methods Workshop"
        affiliation_quote = f"This invented document is attributed to {organization}; this is not a real institution."
        papers[paper_id] = {
            "id": paper_id, "title": title, "short_name": short, "year": int(published[:4]), "date": published,
            "url": "", "authors": ["Synthetic author"], "abstract": quote,
            "affiliations": [{"name": organization, "quote": affiliation_quote, "url": ""}],
            "source_status": "synthetic_demo",
            "passages": [{"id": paper_id + "_passage", "text": quote, "location": "Synthetic source passage", "url": ""},
                         {"id": paper_id + "_affiliation", "text": affiliation_quote, "location": "Synthetic attribution", "url": ""}],
        }
        nodes.append({
            "id": paper_id, "short_name": short, "group_ids": [group], "problem": problem,
            "mechanism": mechanism, "solves": solves, "results": "Illustrative behavior in a fictional example; no empirical research result.",
            "limitations": [limitation], "assumptions": ["All records and operations belong to a deliberately simplified fictional example."],
            "uncertainties": ["This demonstration does not evaluate scientific discovery quality."],
            "evidence": [{"id": paper_id + "_ev", "quote": quote}],
        })
    edges = []

    def edge(source, target, problem, mechanism, kind="addresses", status="supported", rationale=""):
        edges.append({"source": source, "target": target, "kind": kind, "problem": problem,
                      "mechanism": mechanism, "consequence": "See the endpoint evidence and retained limitation.",
                      "evidence_ids": [source + "_ev", target + "_ev"], "status": status,
                      "rationale": rationale or "The synthetic passages explicitly describe the relevant design and its limitation.",
                      "conditions": ["Within the fictional ledger example only."]})

    edge("ledger", "window", "Retaining every record expands storage.", "Discard records outside a fixed window.")
    edge("ledger", "summary", "Retaining every record expands storage.", "Replace individual records with category totals.")
    if stage >= 2:
        edge("summary", "correction", "Aggregation loses the identity needed to replace earlier contributions.", "Keep selected keys in a correction table.")
        edge("summary", "sketch", "Aggregated totals conceal selected inconsistent updates.", "Maintain an audit signature.", "challenges")
        edge("window", "correction", "Windowed records are lost after eviction.", "A bounded correction table may recover older records.",
             status="hypothesis" if stage == 2 else "rejected",
             rationale="Unverified: no source supports recovery of discarded records." if stage == 2 else "Retracted: the correction table cannot reconstruct evicted records. The earlier connection overstated its scope.")
    if stage >= 3:
        edge("correction", "hybrid", "A correction table alone provides no mismatch signal.", "Combine retained correction entries with audit signals.", "builds_on")
        edge("sketch", "hybrid", "Detection does not itself repair an aggregate.", "Use the mismatch signal to inspect retained correction entries.", "builds_on")
        edge("hybrid", "audit", "Bounded storage was being treated as sufficient evidence of bounded work.", "Count verification operations separately.", "challenges")
    proposal = {
        "groups": [
            {"id": "storage", "label": "Bound stored history", "description": "Synthetic designs trade individual records for limited storage."},
            {"id": "correction", "label": "Recover selected corrections", "description": "Synthetic follow-ups address limitations created by aggregation."},
            {"id": "audit", "label": "Audit hidden assumptions", "description": "Synthetic checks retain counterexamples rather than forcing a longer chain."},
        ],
        "nodes": nodes, "edges": edges,
        "gaps": [{"id": "gap_eviction", "description": "No fictional design shown here reconstructs arbitrary evicted records.", "paper_ids": ["window"]}],
        "review_notes": ["SYNTHETIC DEMO: every work, institution, quotation, and result is invented for interface testing.",
                         "The branching, same-date nodes, multi-parent links, and retracted interpretation are intentional UI examples."],
    }
    return build_snapshot(proposal, papers, previous, "ledger", DEMO_SCOPE, iteration, demo=True)
