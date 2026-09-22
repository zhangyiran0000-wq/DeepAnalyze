"""Public data contracts and bounded research-run settings."""

from __future__ import annotations

DEFAULT_CONFIG = {
    "max_iterations": 10,
    "candidates_per_round": 30,
    "read_per_round": 10,
    "max_model_calls": 100,
    "max_seconds": 18000,
    "model": "gpt-5.6-luna",
    "language": "zh",
}

_BOUNDS = {
    "max_iterations": (1, 20),
    "candidates_per_round": (1, 60),
    "read_per_round": (1, 30),
    "max_model_calls": (1, 100),
    "max_seconds": (10, 18000),
}


def normalize_config(config: dict | None = None) -> dict:
    """Validate rather than silently expand a user's spending limits."""
    config = config or {}
    if not isinstance(config, dict):
        raise ValueError("Run configuration must be an object.")
    # Accept legacy saved configs while removing the retired keyword control.
    config = {key: value for key, value in config.items() if key != "scope_keywords"}
    unknown = set(config) - set(DEFAULT_CONFIG)
    if unknown:
        raise ValueError("Unknown run configuration field.")
    result = dict(DEFAULT_CONFIG)
    for key, (low, high) in _BOUNDS.items():
        value = config.get(key, result[key])
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"{key} must be an integer between {low} and {high}.")
        result[key] = value
    model = config.get("model", DEFAULT_CONFIG["model"])
    if not isinstance(model, str) or len(model) > 120 or any(ord(c) < 32 for c in model):
        raise ValueError("Invalid model name.")
    result["model"] = model.strip() or DEFAULT_CONFIG["model"]
    language = config.get("language", DEFAULT_CONFIG["language"])
    if language not in ("zh", "en"):
        raise ValueError("Choose Chinese (zh) or English (en).")
    result["language"] = language
    return result


EXPLORATION_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "scope": {"type": "string"},
        "candidate_rationales": {"type": "array", "maxItems": 30, "items": {
            "type": "object", "additionalProperties": False,
            "properties": {key: {"type": "string"} for key in (
                "paper_id", "anchor_id", "current_claim", "different_story", "selection_reason") } | {
                "problem_relation": {"type": "string", "enum": ["same_problem", "mechanism_consequence", "necessary_background", "shared_domain_only", "uncertain"]}},
            "required": ["paper_id", "anchor_id", "current_claim", "different_story", "selection_reason", "problem_relation"],
        }},
        "challenges": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "selected_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
    },
    "required": ["scope", "candidate_rationales", "challenges", "selected_ids"],
}


def _object(properties):
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}


_STRING = {"type": "string"}
_STRINGS = {"type": "array", "items": _STRING}
_GROUP = _object({
    "id": _STRING, "label": _STRING, "description": _STRING,
    "common_problem": _STRING, "progression": _STRING, "open_problem": _STRING,
    "member_ids": _STRINGS, "merge_from": _STRINGS, "separation_reason": _STRING,
    "core_concept": _STRING,
    "label_nouns": {"type": "array", "items": _STRING, "minItems": 1, "maxItems": 5},
    "explanatory_claim": _object({"constraint": _STRING, "mechanism": _STRING, "consequence": _STRING}),
    "spine": {"type": "array", "items": _object({"source": _STRING, "target": _STRING, "claim_connection": _STRING})},
    "member_support": {"type": "array", "items": _object({"paper_id": _STRING, "claim_connection": _STRING, "evidence_ids": _STRINGS})},
})
_COMPARISON = _object({
    "source": _STRING, "target": _STRING, "shared_problem": _STRING,
    "earlier_limitation": _STRING, "later_change": _STRING, "remaining_gap": _STRING,
    "relation": {"type": "string", "enum": ["progression", "alternative", "complementary", "unrelated", "insufficient_evidence"]},
    "group_action": {"type": "string", "enum": ["merge", "keep_separate", "uncertain"]},
    "rationale": _STRING, "evidence_ids": _STRINGS,
})
_EVIDENCE = _object({"id": _STRING, "quote": _STRING})
_NODE = _object({
    "id": _STRING, "short_name": _STRING, "group_ids": _STRINGS,
    "problem": _STRING, "mechanism": _STRING, "solves": _STRING, "results": _STRING,
    "limitations": _STRINGS, "assumptions": _STRINGS, "uncertainties": _STRINGS,
    "evidence": {"type": "array", "items": _EVIDENCE},
    "research_observations": {"type": "array", "maxItems": 10, "items": _object({
        "kind": {"type": "string", "enum": ["claimed_problem", "demonstrated_gain", "evaluation_protocol", "limitation", "positioning"]},
        "statement": _STRING,
        "basis": {"type": "string", "enum": ["author_claim", "reported_experiment", "model_inference", "unknown"]},
        "evidence_ids": _STRINGS})},
})
_EDGE = _object({
    "source": _STRING, "target": _STRING,
    "kind": {"type": "string", "enum": ["addresses", "builds_on", "challenges", "related"]},
    "problem": _STRING, "mechanism": _STRING, "consequence": _STRING,
    "evidence_ids": _STRINGS,
    "status": {"type": "string", "enum": ["supported", "hypothesis", "rejected"]},
    "rationale": _STRING, "conditions": _STRINGS,
    "historical_influence": {"type": "string", "enum": ["documented", "unknown", "not_claimed"]},
})
_GAP = _object({"id": _STRING, "description": _STRING, "paper_ids": _STRINGS})

CONSOLIDATION_SCHEMA = _object({"groups": {"type": "array", "items": _GROUP}, "review_notes": _STRINGS})
_DISPOSITION = _object({"paper_id": _STRING, "status": {"type": "string", "enum": ["included", "deferred", "out_of_scope"]}, "reason": _STRING})

SYNTHESIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "update_mode": {"type": "string", "enum": ["incremental"]},
        "dispositions": {"type": "array", "items": _DISPOSITION},
        "scope": {"type": "string"},
        "groups": {"type": "array", "items": _GROUP},
        "comparisons": {"type": "array", "items": _COMPARISON},
        "nodes": {"type": "array", "items": _NODE},
        "edges": {"type": "array", "items": _EDGE},
        "gaps": {"type": "array", "items": _GAP},
        "review_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["update_mode", "dispositions", "scope", "groups", "comparisons", "nodes", "edges", "gaps", "review_notes"],
}
